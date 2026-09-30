"""HTTP callbacks and the guarded live media WebSocket."""

from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from starlette.datastructures import FormData
from websockets.exceptions import ConnectionClosedOK

from voice_bot.config import Configuration, load_configuration
from voice_bot.live_bridge import run_live_media_bridge
from voice_bot.openai_realtime import (
    OpenAIRealtimeSession,
    connect_openai_websocket,
)
from voice_bot.runs import (
    DEFAULT_OUTPUT_ROOT,
    CallStatus,
    RunRecordError,
    attach_completed_recording,
    update_call_status,
)
from voice_bot.scenarios import ScenarioError, get_scenario
from voice_bot.twilio_security import (
    TwilioRequestValidationError,
    public_request_url,
    validate_twilio_signature,
)
from voice_bot.twiml import TwimlConfigurationError, build_stream_twiml


app = FastAPI(
    title="Pretty Good AI Voice-Agent Assessment Bot",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the local application is running."""
    return {"status": "ok"}


class SimulatedCallStatusEvent(BaseModel):
    """A fake call-status event used only during local development."""

    call_id: str
    scenario_id: str
    status: CallStatus


class SimulatedCallStatusResponse(BaseModel):
    """Acknowledgement returned for a valid simulated event."""

    accepted: bool
    call_id: str
    scenario_id: str
    status: CallStatus


class SimulatedAnswerRequest(BaseModel):
    """Input for generating test-only TwiML locally."""

    scenario_id: str
    public_base_url: str


@app.post("/test/call-status")
def simulated_call_status(
    event: SimulatedCallStatusEvent,
) -> SimulatedCallStatusResponse:
    """Validate and acknowledge a fake call-status event."""
    try:
        get_scenario(event.scenario_id)
    except ScenarioError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return SimulatedCallStatusResponse(
        accepted=True,
        call_id=event.call_id,
        scenario_id=event.scenario_id,
        status=event.status,
    )


@app.post("/test/twilio/answer", response_class=Response)
def simulated_twilio_answer(request: SimulatedAnswerRequest) -> Response:
    """Return fake answer instructions without opening an audio stream."""
    try:
        twiml = build_stream_twiml(request.scenario_id, request.public_base_url)
    except ScenarioError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TwimlConfigurationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return Response(content=twiml, media_type="application/xml")


async def _require_signed_http_request(
    request: Request,
    configuration: Configuration,
) -> FormData:
    """Authenticate one form-encoded Twilio callback."""
    parameters: FormData | dict[str, str] = {}
    if request.method == "POST":
        body = (await request.body()).decode("utf-8")
        parameters = FormData(parse_qsl(body, keep_blank_values=True))
    url = public_request_url(
        configuration.public_base_url or "",
        request.url.path,
        request.url.query,
    )
    try:
        validate_twilio_signature(
            auth_token=configuration.twilio_auth_token,
            signature=request.headers.get("X-Twilio-Signature"),
            url=url,
            parameters=parameters,
        )
    except TwilioRequestValidationError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    return FormData(parameters)


TWILIO_CALL_STATUSES = {
    "queued": CallStatus.QUEUED,
    "ringing": CallStatus.RINGING,
    "in-progress": CallStatus.ANSWERED,
    "completed": CallStatus.COMPLETED,
    "busy": CallStatus.FAILED,
    "failed": CallStatus.FAILED,
    "no-answer": CallStatus.FAILED,
    "canceled": CallStatus.FAILED,
}


@app.post("/twilio/call-status", status_code=204)
async def twilio_call_status(request: Request) -> Response:
    """Authenticate and persist one Twilio call lifecycle update."""
    configuration = load_configuration()
    if not configuration.enable_real_calls:
        raise HTTPException(status_code=403, detail="Real calls are disabled.")

    parameters = await _require_signed_http_request(request, configuration)
    call_id = parameters.get("CallSid")
    twilio_status = parameters.get("CallStatus")
    status = TWILIO_CALL_STATUSES.get(str(twilio_status))
    if not call_id or status is None:
        raise HTTPException(status_code=422, detail="Invalid Twilio call status event.")

    try:
        update_call_status(DEFAULT_OUTPUT_ROOT / str(call_id), status)
    except RunRecordError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)


@app.post("/twilio/recording-status", status_code=204)
async def twilio_recording_status(request: Request) -> Response:
    """Authenticate and retain one completed Twilio recording reference."""
    configuration = load_configuration()
    if not configuration.enable_real_calls:
        raise HTTPException(status_code=403, detail="Real calls are disabled.")

    parameters = await _require_signed_http_request(request, configuration)
    call_id = parameters.get("CallSid")
    recording_id = parameters.get("RecordingSid")
    if (
        not call_id
        or not recording_id
        or parameters.get("RecordingStatus") != "completed"
    ):
        raise HTTPException(status_code=422, detail="Invalid recording status event.")

    try:
        attach_completed_recording(
            DEFAULT_OUTPUT_ROOT / str(call_id),
            str(recording_id),
        )
    except RunRecordError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)


@app.api_route("/twilio/answer", methods=["GET", "POST"], response_class=Response)
async def twilio_answer(request: Request, scenario_id: str) -> Response:
    """Tell an authorized Twilio call where to open its media stream."""
    configuration = load_configuration()
    if not configuration.enable_real_calls:
        raise HTTPException(status_code=403, detail="Real calls are disabled.")
    if not configuration.public_base_url:
        raise HTTPException(status_code=503, detail="PUBLIC_BASE_URL is missing.")
    await _require_signed_http_request(request, configuration)
    try:
        twiml = build_stream_twiml(scenario_id, configuration.public_base_url)
    except ScenarioError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TwimlConfigurationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/twilio/media")
async def twilio_media(websocket: WebSocket) -> None:
    """Relay an authorized phone stream to a fictional OpenAI patient."""
    configuration = load_configuration()
    if not configuration.enable_real_calls or not configuration.openai_api_key:
        await websocket.close(code=1008, reason="Live voice is disabled or unconfigured.")
        return

    try:
        url = public_request_url(
            configuration.public_base_url or "",
            websocket.url.path,
            websocket.url.query,
            websocket=True,
        )
        validate_twilio_signature(
            auth_token=configuration.twilio_auth_token,
            signature=websocket.headers.get("X-Twilio-Signature"),
            url=url,
            allow_trailing_slash=True,
        )
    except TwilioRequestValidationError:
        await websocket.close(code=1008, reason="Invalid Twilio signature.")
        return

    await websocket.accept()
    session = OpenAIRealtimeSession(
        configuration.openai_api_key,
        connector=connect_openai_websocket,
    )
    try:
        await run_live_media_bridge(websocket, session)
    except (WebSocketDisconnect, ConnectionClosedOK):
        await session.close()
