import asyncio
import logging
from fastapi import FastAPI, APIRouter, HTTPException, Body, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any

from src.api.schemas import ReversalRequest, ReversalResponse, ErrorResponse, ReversalInitiatedResponse, DecisionExplanationResponse
from src.core.reversibility.snapshot_service import SnapshotService
from src.core.reversibility.reversal_manager import ReversalManager, ReversalResult
from src.core.agent_lifecycle_controller import AgentLifecycleController
from src.core.reversibility.file_snapshot_storage import FileSnapshotStorage

# Attempt to import graph creation functions - this might need adjustment
# depending on project structure and how these are exposed.
try:
    from src.kfm_agent import get_graph_creation_functions
except ImportError:
    logging.warning("Could not import get_graph_creation_functions from src.kfm_agent. API will have placeholder graph functions.")
    # Define placeholder functions if import fails
    def placeholder_create_graph_fn():
        raise NotImplementedError("Graph creation function not available.")
    def placeholder_create_debug_graph_fn():
        raise NotImplementedError("Debug graph creation function not available.")
    
    get_graph_creation_functions = lambda: (placeholder_create_graph_fn, placeholder_create_debug_graph_fn)

# --- Global instances (for simplicity in this example; consider dependency injection for a larger app) ---
# Configuration
SNAPSHOT_BASE_PATH = "./kfm_snapshots_api" # Example path, configure as needed

# Instantiate services and controllers
try:
    snapshot_storage = FileSnapshotStorage(base_path=SNAPSHOT_BASE_PATH)
    snapshot_service_instance = SnapshotService(storage_backend=snapshot_storage)
    
    create_fn, create_debug_fn = get_graph_creation_functions()
    # TODO: The AgentLifecycleController itself calls _initialize_graph in __init__
    # which might not be ideal if the graph functions aren't fully ready or cause side effects.
    # For an API server, we might want a lazier initialization or a way to pass a pre-configured app.
    # For now, let's assume it works or a placeholder is used.
    agent_lifecycle_controller_instance = AgentLifecycleController(
        create_graph_fn=create_fn,
        create_debug_graph_fn=create_debug_fn,
        debug_graph=False # Default to non-debug for API
    )
    
    reversal_manager_instance = ReversalManager(
        snapshot_service=snapshot_service_instance,
        lifecycle_controller=agent_lifecycle_controller_instance
    )
    
    api_ready = True
except Exception as e:
    logging.error(f"Failed to initialize core services for API: {e}", exc_info=True)
    api_ready = False
    # Define dummy instances if initialization fails so the API can start and report errors
    reversal_manager_instance = None 
    # Add a placeholder for the explanation service if core services failed, 
    # though it doesn't have complex dependencies like the others.
    local_explanation_service_instance = None 

# Instantiate LocalKfmExplanationService
# It's relatively lightweight, so direct instantiation here should be okay.
# If it becomes more complex, consider dependency injection.
try:
    from src.transparency.local_explanation_service import LocalKfmExplanationService, DEFAULT_SEMANTIC_LOG_FILE, DEFAULT_DECISION_EVENT_TAG
    local_explanation_service_instance = LocalKfmExplanationService() # Uses default log path
    # api_ready check will cover if this part fails, but this service is simpler.
except ImportError as ie:
    logging.error(f"Failed to import LocalKfmExplanationService: {ie}. Explanation API will be disabled.", exc_info=True)
    local_explanation_service_instance = None
except Exception as e_service:
    logging.error(f"Failed to initialize LocalKfmExplanationService: {e_service}. Explanation API might be impaired.", exc_info=True)
    # It might still work with a default path if the class loaded but init failed for other reasons.
    # For safety, let's nullify it.
    local_explanation_service_instance = None

# --- End Global instances ---

app = FastAPI(
    title="KFM Agent API",
    description="API for interacting with the KFM Agent, including reversal operations.",
    version="0.1.0"
)

router = APIRouter()

@router.post("/reversal", 
             response_model=ReversalResponse,
             responses={
                 202: {"model": ReversalInitiatedResponse, "description": "Reversal process initiated"},
                 400: {"model": ErrorResponse, "description": "Invalid request"},
                 500: {"model": ErrorResponse, "description": "Internal server error"},
                 503: {"model": ErrorResponse, "description": "Service unavailable (core components failed to initialize)"}
             })
async def trigger_reversal_endpoint(request: ReversalRequest = Body(...)):
    if not api_ready or reversal_manager_instance is None:
        raise HTTPException(status_code=503, detail="Core services for reversal are not available.")

    try:
        result: Optional[ReversalResult] = None
        target_identifier_for_response: Optional[str] = None

        if request.revert_last_fuck:
            if not request.original_correlation_id:
                raise HTTPException(status_code=400, detail="original_correlation_id is required when revert_last_fuck is true.")
            logging.info(f"API: Received request to revert last fuck action for correlation ID: {request.original_correlation_id}")
            result = await reversal_manager_instance.revert_last_fuck_action(request.original_correlation_id)
            target_identifier_for_response = result.snapshot_id_used if result and result.snapshot_id_used else request.original_correlation_id
        
        elif request.snapshot_id:
            logging.info(f"API: Received request to revert to snapshot ID: {request.snapshot_id}")
            result = await reversal_manager_instance.revert_to_snapshot(request.snapshot_id)
            target_identifier_for_response = result.snapshot_id_used if result else request.snapshot_id
        
        else:
            # Should be caught by Pydantic model validation, but as a safeguard:
            raise HTTPException(status_code=400, detail="Invalid request: Must specify either snapshot_id or revert_last_fuck.")

        if result is None: # Should not happen if logic above is correct
             raise HTTPException(status_code=500, detail="Reversal action did not produce a result.")

        if result.success:
            logging.info(f"API: Reversal successful for {target_identifier_for_response}. Message: {result.message}")
            return ReversalResponse(
                status="success", 
                snapshot_id=target_identifier_for_response, 
                message=result.message
            )
        else:
            logging.error(f"API: Reversal failed for {target_identifier_for_response}. Error: {result.message}")
            # Distinguish between client error (e.g. snapshot not found) and server error
            if "not found" in (result.message or "").lower():
                 raise HTTPException(status_code=404, detail=result.message or "Snapshot not found or reversal prerequisite failed.")
            raise HTTPException(status_code=500, detail=result.message or "Reversal process failed.")

    except HTTPException: # Re-raise HTTPExceptions
        raise
    except ValueError as ve: # From Pydantic validation if not caught by FastAPI
        logging.warning(f"API: Validation error in reversal request: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logging.error(f"API: Unexpected error during reversal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.get("/explain-decision",
            response_model=DecisionExplanationResponse,
            responses={
                404: {"model": ErrorResponse, "description": "Decision context not found"},
                500: {"model": ErrorResponse, "description": "Internal server error"},
                503: {"model": ErrorResponse, "description": "Explanation service unavailable"}
            },
            summary="Get Explanation for KFM Decision",
            tags=["KFM Agent Insights"])
async def get_decision_explanation(
    run_id: str = Query(..., description="The run_id of the agent execution to inspect."),
    decision_index: Optional[int] = Query(0, description="The 0-based index of the decision to explain (default: 0)."),
    log_file: Optional[str] = Query(None, description=f"Path to the semantic log file. If not provided, uses default: {DEFAULT_SEMANTIC_LOG_FILE}"),
    event_tag: Optional[str] = Query(DEFAULT_DECISION_EVENT_TAG, description=f"The event tag identifying a KFM decision (default: {DEFAULT_DECISION_EVENT_TAG}).")
):
    """
    Retrieves and formats an explanation for a specific KFM agent decision based on semantic logs.
    """
    if not local_explanation_service_instance:
        raise HTTPException(status_code=503, detail="Local Explanation Service is not available.")

    # If a custom log_file is provided via query param, instantiate a new service for this request
    # Otherwise, use the global instance with its default log file.
    explainer_to_use = local_explanation_service_instance
    if log_file:
        try:
            # This assumes LocalKfmExplanationService can be re-instantiated safely.
            explainer_to_use = LocalKfmExplanationService(log_file_path=log_file)
        except Exception as e_inst:
            logging.error(f"API: Failed to instantiate LocalKfmExplanationService with custom log file '{log_file}': {e_inst}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error initializing explanation service with custom log file: {str(e_inst)}")

    try:
        context = explainer_to_use.get_kfm_decision_context(
            run_id=run_id,
            decision_event_tag=event_tag,
            decision_index=decision_index
        )
    except Exception as e_ctx:
        logging.error(f"API: Error getting decision context for run_id '{run_id}': {e_ctx}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving decision context: {str(e_ctx)}")

    if not context:
        raise HTTPException(
            status_code=404, 
            detail=f"Decision context not found for run_id='{run_id}' with decision_index={decision_index}, event_tag='{event_tag}' using log file '{explainer_to_use.log_file_path}'."
        )
    
    try:
        formatted_explanation = explainer_to_use.format_decision_explanation(context)
    except Exception as e_fmt:
        logging.error(f"API: Error formatting decision explanation for run_id '{run_id}': {e_fmt}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error formatting decision explanation: {str(e_fmt)}")

    return DecisionExplanationResponse(
        run_id=run_id,
        decision_index_found=context.get("decision_index_found", decision_index if decision_index is not None else 0),
        formatted_explanation=formatted_explanation,
        log_file_used=explainer_to_use.log_file_path,
        event_tag_used=event_tag
    )

app.include_router(router, prefix="/agent/v1")

# Example for running this app: uvicorn src.api.main:app --reload
if __name__ == "__main__":
    import uvicorn
    # This is for local development running this file directly.
    # Production deployment would use a proper ASGI server like Uvicorn or Hypercorn.
    # Ensure SNAPSHOT_BASE_PATH directory exists or is creatable by FileSnapshotStorage
    
    # Make sure the snapshot directory exists
    import os
    if not os.path.exists(SNAPSHOT_BASE_PATH):
        try:
            os.makedirs(SNAPSHOT_BASE_PATH)
            logging.info(f"Created snapshot directory for API: {SNAPSHOT_BASE_PATH}")
        except OSError as e:
            logging.error(f"Could not create snapshot directory {SNAPSHOT_BASE_PATH}: {e}")
            # Decide if to exit or let FileSnapshotStorage handle it

    if not api_ready:
        logging.critical("API cannot start properly because core services failed to initialize. Check logs.")
        # exit(1) # Or let it run and return 503s

    logging.info(f"Starting KFM Agent API server. API Ready: {api_ready}")
    uvicorn.run(app, host="0.0.0.0", port=8000) 