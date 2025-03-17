from fastapi import FastAPI, File, UploadFile
from .utils import util
from .convert_final_final import convert
from .convert_last import convert as convert2
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.background import BackgroundTask
import asyncio
import json
import uvicorn


class TimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Set a long timeout for specific endpoints
        if request.url.path == "/api/py/convert":
            # Use a custom event loop with a longer timeout
            try:
                response = await asyncio.wait_for(call_next(request), timeout=300.0)
                return response
            except asyncio.TimeoutError:
                return JSONResponse(
                    status_code=504,
                    content={"error": "Operation timed out after 300 seconds"},
                )
        return await call_next(request)


### Create FastAPI instance with custom docs and openapi url
app = FastAPI(docs_url="/api/py/docs", openapi_url="/api/py/openapi.json")

# Add middlewares
app.add_middleware(TimeoutMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def process_pdf(pdf_bytes):
    """Process PDF in background"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, convert2, pdf_bytes)


@app.get("/api/py/helloFastApi")
def hello_fast_api():
    """This is a test!"""
    return {"message": util()}


@app.post("/api/py/convert")
async def convert_pdf_to_markdown(file: UploadFile = File(...)):
    """Convert a PDF file to HTML"""
    # Read file in memory
    pdf_bytes = await file.read()

    try:
        # Process PDF with timeout
        tiptap_doc = await asyncio.wait_for(process_pdf(pdf_bytes), timeout=300.0)

        # Return as streaming response to maintain connection
        async def generate():
            yield json.dumps(tiptap_doc).encode("utf-8")

        return StreamingResponse(
            generate(),
            media_type="application/json",
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504, content={"error": "Operation timed out after 300 seconds"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
