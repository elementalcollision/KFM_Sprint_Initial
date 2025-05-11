import json
import logging
from typing import Dict, Any, Optional, Literal, Tuple, List, ClassVar
from uuid import UUID
from src.core.llm_logging import KfmPlannerCallbackHandler, get_configured_logger
# Import custom exceptions
from src.core.kfm_llm_exceptions import (
    KfmPlannerError,
    KfmValidationError,
    KfmJsonConversionError,
    KfmOutputParsingError,
    KfmInvocationError
)

from pydantic import BaseModel, Field, ValidationError, field_validator
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable, RunnablePassthrough, RunnableSerializable
from langchain_core.exceptions import OutputParserException as LangchainOutputParserException
from httpx import TimeoutException, NetworkError
from openai import APIError, RateLimitError, APITimeoutError, APIConnectionError, APIStatusError
import os
from dotenv import load_dotenv
from google.generativeai import GenerativeModel # Assuming direct Google AI usage
# from langchain_google_genai import ChatGoogleGenerativeAI # Alternative if using LangChain
from .state import KFMAgentState # Corrected import from .state
from .component_registry import ComponentRegistry # Corrected import from .component_registry
from .memory.chroma_manager import ChromaMemoryManager # Import the manager
from .memory.models import AgentQueryContext # Import AgentQueryContext
from .prompt_manager import get_global_prompt_manager, PromptManager # Added PromptManager
import re
from src.core.ethical_manager_instance import get_ecm_instance # Added import for ECM
from src.core.ethical_config_manager_mock import EthicalConfigManagerMock # Use the mock type for now

# --- Snapshot Service Imports ---
from .reversibility.file_snapshot_storage import FileSnapshotStorage
from .reversibility.snapshot_service import SnapshotService
import asyncio # For running async snapshot calls if in sync context (though decide_kfm_action is sync)

# Attempt to import Chat Models - handle gracefully if unavailable
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None
    print("Warning: langchain-google-genai not installed. Google models unavailable.")

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None
    print("Warning: langchain-openai not installed. OpenAI models unavailable.")

try:
    from langchain_cerebras import ChatCerebras
except ImportError:
    ChatCerebras = None
    print("Warning: langchain-cerebras not installed. Cerebras models unavailable.")

from datetime import datetime, timezone # Added datetime and timezone

# Load environment variables from .env file
load_dotenv()

# --- Pydantic Model for LLM Output Validation ---

class KFMDecision(BaseModel):
    """Pydantic model to validate the JSON output structure from the KFMPlannerLlm."""
    action: Literal["Kill", "Fuck", "Marry", "No Action"]
    component: Optional[str] = None
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    error: Optional[str] = None # For capturing parsing/validation errors from LLM output

    @field_validator('component')
    def check_component_for_action(cls, v, values):
        # Pydantic v2 uses values.data to access other fields
        if 'action' in values.data:
            action = values.data['action']
            if action in ['Marry', 'Fuck'] and v is None:
                raise ValueError("Component cannot be None for 'Marry' or 'Fuck' actions.")
            if action == 'Kill' and v is not None:
                # For Kill, component *can* be specified to indicate which one is killed.
                # If the intent is that component MUST be None for Kill, then this check is needed.
                # Current KFM logic often implies killing a specific underperforming component.
                # Let's assume for now that Kill can have a component.
                # If component MUST be None for Kill, uncomment below:
                # raise ValueError("Component must be None for 'Kill' action.")
                pass 
        return v

    def to_dict(self) -> Dict[str, Any]: # Added Any to Dict value type
        """Returns a dictionary representation of the model."""
        return self.model_dump(exclude_none=True)

# --- Optimized KFM Prompt Templates ---
# Define Prompt IDs
KFM_LLM_SYSTEM_DEFAULT_ID = "kfm_llm_system_default"
KFM_LLM_HUMAN_DEFAULT_ID = "kfm_llm_human_default"
KFM_LLM_SYSTEM_CEREBRAS_ID = "kfm_llm_system_cerebras"

OPTIMIZED_KFM_SYSTEM_PROMPT = """You are KFMPlannerLlm. Decide the KFM action (marry, fuck, kill) based on task requirements and component performance. Output ONLY the specified JSON.

Rules:
1. Marry: If component meets BOTH min_accuracy AND max_latency. To qualify for Marry, a component's accuracy MUST be greater than or equal to `min_accuracy` AND its latency MUST be less than or equal to `max_latency`. Both conditions are mandatory. Pay close attention to the `(Meets Acc Requirement: ...)` and `(Meets Lat Requirement: ...)` indicators provided for each component. Use these indicators directly when evaluating the Marry and Fuck rules. Tiebreaker: highest accuracy, then lowest latency.
   **Marry Decision Process:**
   1. Identify all components.
   2. For each component, check if `accuracy >= min_accuracy`.
   3. For each component, check if `latency <= max_latency`.
   4. Filter the list to components where BOTH checks (2 and 3) are TRUE. These are Marry candidates.
   5. If Marry candidates exist:
      a. Find the candidate(s) with the highest `accuracy`.
      b. Among those, find the candidate with the lowest `latency`.
      c. Select this component for the 'marry' action. Provide reasoning based on meeting both criteria and tiebreakers if applied.
   6. If NO Marry candidates exist, proceed to Fuck decision process.
2. Fuck: If NO component qualifies for Marry, choose if component meets EITHER min_accuracy OR max_latency. Use the pre-calculated boolean indicators. Prefer components where `supports_reversibility` is true if other factors are equal. Tiebreaker: highest accuracy, then lowest latency.
3. Kill: If NO component qualifies for Marry or Fuck.

Inputs Provided:
- task_name
- min_accuracy (float) - Note: `min_accuracy` can be 0.0. A component with `accuracy >= 0.0` is considered to meet the accuracy requirement.
- max_latency (float)
- components: A dictionary where keys are component names (strings) and values are dictionaries with 'accuracy' (float), 'latency' (float), and 'supports_reversibility' (boolean). Example: {{"component_A": {{"accuracy": 0.95, "latency": 50, "supports_reversibility": true}}}}

Error Handling:
- Missing requirements: Kill, reason "missing requirements".
- No components: Kill, reason "no components".
- Perfect tie: Choose alphabetically first component name.

Output JSON Format (ONLY this JSON):
{{ "action": "ACTION_TYPE", "component": "COMPONENT_NAME_OR_NULL", "reasoning": "REASONING_TEXT", "confidence": CONFIDENCE_SCORE_FLOAT }}
IMPORTANT: If action is 'kill', component MUST be JSON null (not the string "null").
"""

# Cerebras-Specific Prompt with stronger reasoning instruction
CEREBRAS_OPTIMIZED_KFM_SYSTEM_PROMPT = """You are KFMPlannerLlm. Decide the KFM action (marry, fuck, kill) based on task requirements and component performance. Output ONLY the specified JSON.

Rules:
1. Marry: If component meets BOTH min_accuracy AND max_latency. To qualify for Marry, a component's accuracy MUST be greater than or equal to `min_accuracy` AND its latency MUST be less than or equal to `max_latency`. Both conditions are mandatory. Pay close attention to the `(Meets Acc Requirement: ...)` and `(Meets Lat Requirement: ...)` indicators provided for each component. Use these indicators directly when evaluating the Marry and Fuck rules. Tiebreaker: highest accuracy, then lowest latency.
   **Marry Decision Process:**
   **CRITICAL: Base your filtering ONLY on the provided `(Meets ... Req: True/False)` boolean indicators.**
   1. Identify all components provided.
   2. For each component, precisely check if `accuracy >= min_accuracy`. Record result (True/False).
   3. For each component, precisely check if `latency <= max_latency`. Record result (True/False).
   4. Filter components: Select ONLY those where BOTH `(Meets Acc Req: True)` AND `(Meets Lat Req: True)` are present in the input. These are the *only* valid Marry candidates.
   5. If one or more Marry candidates exist:
      a. Find the candidate(s) with the absolute highest `accuracy` value among the candidates.
      b. If there's a tie in accuracy, find the candidate among those tied with the absolute lowest `latency` value.
      c. Select this single best component for the 'marry' action. Clearly state in reasoning how it met BOTH requirements and mention tiebreakers if used.
   6. If NO Marry candidates exist (no component met BOTH criteria), proceed to evaluate for the Fuck action.
2. Fuck: If NO component qualifies for Marry, choose if component meets EITHER min_accuracy OR max_latency. Use the pre-calculated boolean indicators. Prefer components where `supports_reversibility` is true if other factors are equal. Tiebreaker: highest accuracy, then lowest latency.
3. Kill: If NO component qualifies for Marry or Fuck.

Inputs Provided:
- task_name
- min_accuracy (float) - Note: `min_accuracy` can be 0.0. A component with `accuracy >= 0.0` is considered to meet the accuracy requirement if its latency also meets the `max_latency` requirement for the Marry rule.
- max_latency (float)
- components: A dictionary where keys are component names (strings) and values are dictionaries with 'accuracy' (float), 'latency' (float), and 'supports_reversibility' (boolean). Example: {{"component_A": {{"accuracy": 0.95, "latency": 50, "supports_reversibility": true}}}}

Error Handling:
- Missing requirements: Kill, reason "missing requirements".
- No components: Kill, reason "no components".
- Perfect tie: Choose alphabetically first component name.

Output JSON Format (ONLY this JSON):
{{ "action": "ACTION_TYPE", "component": "COMPONENT_NAME_OR_NULL", "reasoning": "REASONING_TEXT", "confidence": CONFIDENCE_SCORE_FLOAT }}
CRITICAL: The 'reasoning' field MUST clearly explain *why* the action was chosen based on the explicit rules and the provided boolean requirement indicators. If action is 'kill', component MUST be JSON null.
"""

OPTIMIZED_KFM_HUMAN_PROMPT = "Task: {task_name}\nMin Accuracy: {min_accuracy}\nMax Latency: {max_latency}\nComponents:\n{components_str_with_indicators}"

# --- LLM-based KFM Planner ---

logger = logging.getLogger(__name__)

# Initialize default prompts in the global manager at module load time
# This ensures they are available even if KFMPlannerLlm is instantiated multiple times
# or if other modules need to reference these specific prompt IDs.
_initial_prompt_manager = get_global_prompt_manager()
_initial_prompt_manager.register_prompt(KFM_LLM_SYSTEM_DEFAULT_ID, OPTIMIZED_KFM_SYSTEM_PROMPT, version=1)
_initial_prompt_manager.register_prompt(KFM_LLM_HUMAN_DEFAULT_ID, OPTIMIZED_KFM_HUMAN_PROMPT, version=1)
_initial_prompt_manager.register_prompt(KFM_LLM_SYSTEM_CEREBRAS_ID, CEREBRAS_OPTIMIZED_KFM_SYSTEM_PROMPT, version=1)

class KFMPlannerLlm(RunnablePassthrough):
    """
    LLM-driven KFM Planner that uses LangChain to decide KFM actions.
    Designed to be a potential replacement for the rule-based KFMPlanner,
    offering more flexible reasoning capabilities.

    Utilizes a tiered fallback mechanism for model selection (default: cerebras -> google -> openai_3_5).
    Includes model-specific prompt tuning (e.g., for Cerebras).

    Known Limitations (based on benchmark `scripts/benchmark_kfm_planner_llm.py`):
    - Achieved 93.75% (15/16) accuracy on the test suite.
    - The single failure occurs in the `test_zero_latency_component` scenario, where the planner
      incorrectly interprets a component with latency=0 as having invalid latency, leading to a Kill decision instead of Marry.
    """
    DEFAULT_MODEL_NAME: ClassVar[str] = "gemini-1.5-flash-latest" # Or your preferred default
    # Define KFM Actions type if not already defined globally
    KfmAction: ClassVar[Literal["Kill", "Marry", "Fuck", "No Action"]] # Type alias for actions
    DEFAULT_SNAPSHOT_STORAGE_PATH: ClassVar[str] = "./kfm_snapshots" # Default path for snapshots
    DEFAULT_MAX_MEMORIES_TO_RETRIEVE: ClassVar[int] = 3 # Added default for max memories

    # Pydantic model_config to allow arbitrary types for complex service objects
    model_config = {
        "arbitrary_types_allowed": True,
        "extra": "allow"  # Allow extra fields not explicitly defined in the model
    }

    # Pydantic model fields (instance variables) - these must be declared with type hints
    component_registry: ComponentRegistry
    memory_manager: Optional[ChromaMemoryManager]
    prompt_manager: Optional[PromptManager]
    snapshot_service: Optional[SnapshotService]
    primary_llm_key_for_logging: str
    # LLMConfig needs to be defined or imported if it's a specific class
    # For now, using Dict[str, Any] as a placeholder for LLMConfig type
    llm_configs: Dict[str, Dict[str, Any]] # Assuming LLMConfig is Dict-like
    runnable_chains: Dict[str, Runnable]
    execution_chain: Runnable # Renamed from 'chain'
    ecm: Optional[EthicalConfigManagerMock]
    max_memories_to_retrieve: int
    model_name: str # Added model_name as an instance field

    def __init__(self, 
                 component_registry: ComponentRegistry, 
                 memory_manager: Optional[ChromaMemoryManager] = None, # Added memory_manager
                 model_name: str = DEFAULT_MODEL_NAME, 
                 google_api_key: Optional[str] = None,
                 prompt_manager: Optional[PromptManager] = None, # Added prompt_manager
                 snapshot_storage_path: str = DEFAULT_SNAPSHOT_STORAGE_PATH, # Added snapshot_storage_path
                 max_memories_to_retrieve: int = DEFAULT_MAX_MEMORIES_TO_RETRIEVE): # Added max_memories
        """
        Initializes the LLM-based KFM Planner.

        Args:
            component_registry (ComponentRegistry): The component registry instance.
            memory_manager (Optional[ChromaMemoryManager]): The memory manager instance.
            model_name (str): The name of the generative model to use.
            google_api_key (Optional[str]): Google API key (if not set via environment).
            prompt_manager (Optional[PromptManager]): An instance of PromptManager. If None, uses global.
            snapshot_storage_path (str): Path for storing KFM snapshots.
            max_memories_to_retrieve (int): Max number of memories to retrieve for context.
        """
        # Initialize attributes that will be passed to super().__init__()
        # These must match the fields declared at the class level for Pydantic validation.
        
        _component_registry = component_registry
        _memory_manager = memory_manager
        _max_memories_to_retrieve = max_memories_to_retrieve
        _model_name = model_name
        _prompt_manager = prompt_manager if prompt_manager else get_global_prompt_manager()
        _ecm = get_ecm_instance()

        _snapshot_service: Optional[SnapshotService] = None
        try:
            _snapshot_storage = FileSnapshotStorage(base_storage_path=snapshot_storage_path)
            _snapshot_service = SnapshotService(snapshot_storage=_snapshot_storage)
            logger.info(f"KFMPlannerLlm: SnapshotService initialized with path: {snapshot_storage_path}")
        except Exception as e:
            logger.error(f"KFMPlannerLlm: Failed to initialize SnapshotService: {e}")
            # _snapshot_service remains None

        # Retrieve prompts
        system_default_template = _prompt_manager.get_prompt(KFM_LLM_SYSTEM_DEFAULT_ID) or OPTIMIZED_KFM_SYSTEM_PROMPT
        human_default_template = _prompt_manager.get_prompt(KFM_LLM_HUMAN_DEFAULT_ID) or OPTIMIZED_KFM_HUMAN_PROMPT
        system_cerebras_template = _prompt_manager.get_prompt(KFM_LLM_SYSTEM_CEREBRAS_ID) or CEREBRAS_OPTIMIZED_KFM_SYSTEM_PROMPT

        _standard_prompt = ChatPromptTemplate.from_messages([
            ("system", system_default_template),
            ("human", human_default_template)
        ])
        _cerebras_prompt = ChatPromptTemplate.from_messages([
            ("system", system_cerebras_template),
            ("human", human_default_template)
        ])
        _parser = JsonOutputParser(pydantic_object=KFMDecision)

        # Initialize LLMs
        _llms: Dict[str, BaseLanguageModel] = {}
        if ChatCerebras and os.getenv("CEREBRAS_API_KEY"):
            try:
                _llms["cerebras"] = ChatCerebras(model="llama3.1-8b", temperature=0)
            except Exception as e:
                print(f"Warning: Failed to initialize Cerebras LLM: {e}")
        if ChatGoogleGenerativeAI and os.getenv("GOOGLE_API_KEY"):
            try:
                _llms["google"] = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0, convert_system_message_to_human=True)
            except Exception as e:
                print(f"Warning: Failed to initialize Google LLM: {e}")
        if ChatOpenAI and os.getenv("OPENAI_API_KEY"):
            try:
                _llms["openai_3_5"] = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
            except Exception as e:
                print(f"Warning: Failed to initialize OpenAI gpt-3.5-turbo LLM: {e}")

        # Build Fallback Chain
        _runnable_chains: Dict[str, Runnable] = {}
        _llm_configs: Dict[str, Dict[str, Any]] = {}
        _primary_llm_key_for_logging = "unknown"
        
        llm_provider_priority = ["cerebras", "google", "openai_3_5"]
        processed_runnable_chains_list: List[Runnable] = []

        for provider_key in llm_provider_priority:
            if provider_key in _llms:
                llm_instance = _llms[provider_key]
                prompt_template_to_use = _cerebras_prompt if provider_key == "cerebras" else _standard_prompt
                chain_segment = prompt_template_to_use | llm_instance
                _runnable_chains[provider_key] = chain_segment
                processed_runnable_chains_list.append(chain_segment)
                
                # Populate llm_configs
                cfg = {}
                if hasattr(llm_instance, 'model_name'): cfg['model_name'] = llm_instance.model_name
                elif hasattr(llm_instance, 'model'): cfg['model_name'] = llm_instance.model # common for openai/google via langchain
                else: cfg['model_name'] = provider_key

                if hasattr(llm_instance, 'temperature'): cfg['temperature'] = llm_instance.temperature
                else: cfg['temperature'] = 0 # Default or placeholder
                _llm_configs[provider_key] = cfg

                if _primary_llm_key_for_logging == "unknown":
                    _primary_llm_key_for_logging = provider_key
        
        if not processed_runnable_chains_list:
            raise RuntimeError("No LLMs could be initialized. KFMPlannerLlm cannot function.")

        _primary_chain_segment = processed_runnable_chains_list[0]
        _fallback_chain_segments = processed_runnable_chains_list[1:]
        _execution_chain_instance: Runnable
        if _fallback_chain_segments:
             _execution_chain_instance = _primary_chain_segment.with_fallbacks(_fallback_chain_segments) | _parser
        else:
             _execution_chain_instance = _primary_chain_segment | _parser

        # Now call super().__init__ with all the required fields
        super().__init__(
            component_registry=_component_registry,
            memory_manager=_memory_manager,
            prompt_manager=_prompt_manager,
            snapshot_service=_snapshot_service,
            primary_llm_key_for_logging=_primary_llm_key_for_logging,
            llm_configs=_llm_configs,
            runnable_chains=_runnable_chains,
            execution_chain=_execution_chain_instance,
            ecm=_ecm,
            max_memories_to_retrieve=_max_memories_to_retrieve,
            model_name=_model_name
            # Note: Other attributes like self.llms, self.standard_prompt, self.parser, etc.,
            # are effectively intermediate build steps or helper attributes if not declared as fields.
            # If they ARE meant to be fields, they must be declared at class level and included here.
            # For now, assuming they are not explicit Pydantic fields of KFMPlannerLlm itself.
        )

        # Set other instance attributes that are not part of Pydantic model fields (if any)
        # For example, if self.llms, self.standard_prompt etc. were needed on the instance
        # for other methods, set them here AFTER super().__init__()
        self.llms = _llms # Store the actual LLM instances if needed by other methods
        self.standard_prompt = _standard_prompt
        self.cerebras_prompt = _cerebras_prompt
        self.parser = _parser
        
        # This 'model' attribute seems to be for direct Google GenAI usage, potentially conflicting
        # or redundant with the Langchain chain. Review if still needed.
        # If `self.model` is a required field by Pydantic (declared at class level),
        # it must be included in the call to super().__init__ above.
        try:
            self.model = GenerativeModel(_model_name) # _model_name is the original model_name arg
            logger.info(f"Initialized KFMPlannerLlm's direct GenerativeModel with: {_model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize KFMPlannerLlm's direct GenerativeModel ({_model_name}): {e}", exc_info=True)
            self.model = None
        self.kfm_callback_handler = None # Placeholder

    def _format_component_data_for_prompt(self, components_details: Dict[str, List[Dict[str, Any]]], requirements: Dict[str, Any]) -> str:
        """Formats component data, including performance, indicators, and reversibility, for the LLM prompt."""
        min_accuracy = requirements.get("min_accuracy", 0.0)
        max_latency = requirements.get("max_latency", float('inf'))

        # components_details is Dict[module_name, List[version_details_dict]]
        # We need to present a flat list of "component instances" (module_name@version) to the LLM.
        
        formatted_components_for_llm: Dict[str, Dict[str, Any]] = {}

        for module_name, versions_list in components_details.items():
            for version_detail in versions_list:
                # Construct a unique key for the LLM, e.g., "MyComponent@1.0.0"
                component_key = f"{module_name}@{version_detail['version']}"
                
                perf_metrics = version_detail.get("performance_metrics", {})
                accuracy = perf_metrics.get("accuracy") 
                latency = perf_metrics.get("latency")
                supports_rev = version_detail.get("supports_reversibility", False)

                component_info_for_llm: Dict[str, Any] = {"supports_reversibility": supports_rev}
                
                if accuracy is not None:
                    component_info_for_llm["accuracy"] = accuracy
                if latency is not None:
                    component_info_for_llm["latency"] = latency
                
                formatted_components_for_llm[component_key] = component_info_for_llm
        
        # The system prompt expects components as a JSON-like string of a dictionary.
        # Example: {{"component_A@1.0": {{"accuracy": 0.95, "latency": 50, "supports_reversibility": true}}, ...}}
        components_json_for_prompt = json.dumps(formatted_components_for_llm)
        
        # Return the JSON string for the system prompt, and also the human-readable parts if needed by other templates
        return components_json_for_prompt # For system prompt

    def _format_retrieved_memories(self, memories: List[Dict]) -> str:
        """Formats a list of retrieved memories into a string for the prompt."""
        if not memories:
            return "No relevant past experiences found."
        
        formatted_string = "Relevant Past Successful Experiences (most similar first):\n"
        for i, mem in enumerate(memories, 1):
            doc = mem.get('document') or mem.get('text')
            metadata = mem.get('metadata', {})
            distance = mem.get('distance')
            
            summary = metadata.get('experience_summary_embedded', doc if doc else "Details not available.")
            action_taken = metadata.get('kfm_action_taken', 'N/A')
            outcome = metadata.get('outcome_success', 'N/A')
            similarity = (1 - distance) * 100 if distance is not None else 'N/A'
            
            formatted_string += f"{i}. [Similarity: {similarity:.1f}%] Action: {action_taken}, Outcome: {outcome}. Summary: {summary}\n"
        return formatted_string

    def _generate_prompt(self, task_name: str, task_requirements: Dict, all_components_details: Dict) -> str:
        """Generates the full prompt for the LLM using current context including component details."""
        logger.debug(f"Generating prompt for task: {task_name}")

        # Determine which system prompt to use based on the model or configuration
        # Example: if self.model_name contains "cerebras", use CEREBRAS_OPTIMIZED_KFM_SYSTEM_PROMPT
        # For now, defaulting to the standard one.
        active_system_prompt_id = KFM_LLM_SYSTEM_DEFAULT_ID
        if "cerebras" in self.model_name.lower(): # Basic check
            active_system_prompt_id = KFM_LLM_SYSTEM_CEREBRAS_ID
        
        system_prompt_template_str = self.prompt_manager.get_prompt(active_system_prompt_id)
        if not system_prompt_template_str:
            logger.warning(f"System prompt ID '{active_system_prompt_id}' not found in PromptManager. Falling back to hardcoded default.")
            system_prompt_template_str = OPTIMIZED_KFM_SYSTEM_PROMPT # Fallback

        human_prompt_template_str = self.prompt_manager.get_prompt(KFM_LLM_HUMAN_DEFAULT_ID)
        if not human_prompt_template_str:
            logger.warning(f"Human prompt ID '{KFM_LLM_HUMAN_DEFAULT_ID}' not found in PromptManager. Falling back to hardcoded default.")
            human_prompt_template_str = OPTIMIZED_KFM_HUMAN_PROMPT # Fallback

        # Format component data using the new structure from all_components_details
        components_str_for_prompt = self._format_component_data_for_prompt(all_components_details, task_requirements)
        
        # Prepare inputs for the human part of the prompt
        human_prompt_inputs = {
            "task_name": task_name,
            "min_accuracy": task_requirements.get("min_accuracy", "N/A"),
            "max_latency": task_requirements.get("max_latency", "N/A"),
            "components_str_with_indicators": components_str_for_prompt # This is now the JSON string
        }

        # Create the prompt template instance
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt_template_str),
            ("human", human_prompt_template_str)
        ])
        
        # Format the prompt with all necessary inputs
        # The `invoke` method of the chain will handle passing the final input dictionary
        # For direct formatting (e.g., logging or debugging the prompt itself):
        try:
            # For ChatPromptTemplate, format_messages is used, then convert to string if needed for logging
            formatted_messages = prompt_template.format_messages(**human_prompt_inputs)
            # Concatenate messages to a single string for logging or simpler non-LangChain LLM calls
            full_prompt_str = "\n".join([msg.content for msg in formatted_messages])
            logger.debug(f"Generated LLM Prompt:\n{full_prompt_str}")
            return full_prompt_str # Or perhaps the formatted_messages if the LLM interface prefers that
        except Exception as e:
            logger.error(f"Error formatting prompt: {e}", exc_info=True)
            raise KfmPlannerError(f"Error formatting prompt: {e}")

    def _parse_llm_output(self, llm_response_text: str) -> KFMDecision:
        """Parses the LLM JSON output into a KFMDecision object, with error handling."""
        try:
            # Attempt to find JSON within potentially noisy output
            match = re.search(r'\{.*?\}', llm_response_text, re.DOTALL)
            if not match:
                logger.error(f"LLM output parsing: No JSON object found in response: {llm_response_text}")
                # Default to 'No Action' or raise a specific parsing error
                # For now, let's try to make it a KFMDecision still, but with an error state
                return KFMDecision(action="No Action", component=None, reasoning="LLM output was not valid JSON.", confidence=0.0, error="No JSON found")
            
            json_str = match.group(0)
            data = json.loads(json_str)
            
            # Validate required fields
            action = data.get('action')
            component = data.get('component') # Can be None
            reasoning = data.get('reasoning')
            confidence = data.get('confidence')

            if not all([action, reasoning is not None, confidence is not None]): # component can be None
                logger.error(f"LLM output parsing: Missing required fields in JSON: {data}")
                return KFMDecision(action="No Action", component=None, reasoning="LLM output missing required fields.", confidence=0.0, error="Missing fields")
            
            if action not in ["Kill", "Fuck", "Marry", "No Action"]:
                logger.error(f"LLM output parsing: Invalid action '{action}' in JSON: {data}")
                return KFMDecision(action="No Action", component=None, reasoning=f"LLM output had invalid action: {action}.", confidence=0.0, error="Invalid action")

            return KFMDecision(
                action=action,
                component=component,
                reasoning=reasoning,
                confidence=float(confidence) # Ensure confidence is float
            )
        except json.JSONDecodeError as e:
            logger.error(f"LLM output parsing: JSONDecodeError: {e}. Response: {llm_response_text}")
            return KFMDecision(action="No Action", component=None, reasoning=f"JSON decoding failed: {e}", confidence=0.0, error="JSONDecodeError")
        except Exception as e:
            logger.error(f"LLM output parsing: Unexpected error: {e}. Response: {llm_response_text}", exc_info=True)
            return KFMDecision(action="No Action", component=None, reasoning=f"Unexpected parsing error: {e}", confidence=0.0, error="Unexpected parsing error")

    async def decide_kfm_action(self, task_name: str, task_requirements: Dict, all_components_performance: Dict) -> Dict:
        """
        Core logic for deciding a KFM action using the configured LLM and chain.
        This is where the main LLM invocation happens.
        Wraps the LLM call with error handling and validation.
        Includes pre-decision and post-decision snapshot triggers.
        """
        current_kfm_agent_state_for_snapshot = {
            "task_name": task_name,
            "task_requirements": task_requirements,
            "all_components_performance": all_components_performance,
            "active_llm_key": self.primary_llm_key_for_logging, # Log which LLM config is active
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if self.memory_manager:
            query_context = AgentQueryContext(
                task_name=task_name,
                current_task_requirements=task_requirements,
                available_components=list(all_components_performance.keys())
            )
            retrieved_memories = self.memory_manager.retrieve_memories(
                query_context=query_context,
                n_results=3,
                where_filter={"outcome_success": "True"} 
            )

            if retrieved_memories:
                current_kfm_agent_state_for_snapshot["retrieved_memories"] = [mem.model_dump() for mem in retrieved_memories]
                logger.info(f"Retrieved {len(retrieved_memories)} memories for the prompt.")
            else:
                logger.info("No relevant memories retrieved.")

        # Take pre-decision snapshot
        if self.snapshot_service:
            logger.debug("KFMPlannerLlm: Taking pre-decision snapshot.")
            try:
                await self.snapshot_service.take_snapshot(
                    trigger="pre_kfm_decision", # Corrected: trigger_event to trigger
                    kfm_agent_state=current_kfm_agent_state_for_snapshot,
                    # component_system_state can be None here or include general system info if available
                    additional_metadata={"stage": "pre_llm_invocation"} # Corrected: metadata to additional_metadata
                )
            except Exception as e_snap:
                logger.error(f"KFMPlannerLlm: Error taking pre-decision snapshot: {e_snap}")
                # Decide if this error should halt the process or just be logged.
                # For now, logging and continuing.

        try:
            # --- Input Validation (moved from _generate_prompt for early exit) ---
            if not task_requirements or not all_components_performance:
                logger.warning("Missing task requirements or component performance data. Defaulting to No Action.")
                # Log an error for missing critical data for decision making
                logger.error("KFMPlannerLlm: Critical data missing (task requirements or component performance), cannot make an informed decision.")
                
                # Defaulting to 'No Action' as per previous logic for missing data
                # but also including an error field to make it explicit in the output
                return KFMDecision(
                    action='No Action', 
                    reasoning='Critical data missing: task requirements or component performance data not provided.', 
                    confidence=0.0, # Confidence is zero as no analysis was performed
                    error="Missing critical input data"
                ).to_dict()

            # Format components with indicators for the prompt
            components_str_with_indicators = self._format_component_data_for_prompt(
                all_components_performance, task_requirements
            )

            # Retrieve and format memories if memory_manager is configured
            formatted_memories = "No relevant past experiences found." # Default if no memory manager or no memories
            if self.memory_manager:
                try:
                    query_context = AgentQueryContext(
                        task_name=task_name,
                        current_task_requirements=task_requirements,
                        available_components=list(all_components_performance.keys())
                    )
                    retrieved_memories = self.memory_manager.retrieve_memories(
                        query_context=query_context,
                        k=self.max_memories_to_retrieve # Use configured k
                    )
                    if retrieved_memories:
                        formatted_memories = self._format_retrieved_memories(retrieved_memories)
                        logger.info(f"Retrieved {len(retrieved_memories)} memories for the prompt.")
                except Exception as e:
                    logger.error(f"Error retrieving memories: {e}")
                    formatted_memories = "Error retrieving past experiences."

            logger.info(f"Invoking KFM LLM chain (primary: '{self.primary_llm_key_for_logging}') for task: {task_name}")
            
            # Invoke the Langchain (LCEL) chain
            llm_decision_obj = self.execution_chain.invoke({
                "task_name": task_name,
                "min_accuracy": task_requirements.get("min_accuracy", 0.0),
                "max_latency": task_requirements.get("max_latency", float('inf')),
                "components_str_with_indicators": components_str_with_indicators,
                "formatted_memories": formatted_memories
            })
            # llm_decision_obj is already a KFMDecision instance due to KFMDecisionOutputParser in the chain

            logger.info(f"LLM decision for task '{task_name}': Action={llm_decision_obj.action}, Component={llm_decision_obj.component}, Confidence={llm_decision_obj.confidence:.2f}")

            # --- Ethical Hook: Post-Planning Review ---
            final_decision_obj = llm_decision_obj # Start with the LLM's decision
            if self.ecm: # Check if EthicalConfigManager is available
                try:
                    decision_context_for_ecm = {
                        "task_name": task_name,
                        "action": llm_decision_obj.action,
                        "component": llm_decision_obj.component,
                        "reasoning": llm_decision_obj.reasoning,
                        "confidence": llm_decision_obj.confidence,
                        "task_requirements": task_requirements,
                        "all_components_performance": all_components_performance,
                        "retrieved_memories": formatted_memories # Include memories if available
                    }
                    # The ECM's post_planning_review can return:
                    # - A KFMDecision object (modified decision)
                    # - False (veto)
                    # - None (approve original)
                    ecm_review_result = self.ecm.post_planning_review(
                        planner_type="KFMPlannerLlm",
                        decision_context=decision_context_for_ecm
                    )

                    if ecm_review_result is False: # Explicit Veto
                        logger.warning(f"Ethical hook VETOED action '{llm_decision_obj.action}' for component '{llm_decision_obj.component}'. Overriding to 'No Action'.")
                        final_decision_obj = KFMDecision(
                            action="No Action",
                            component=None, # Veto means no component either
                            reasoning=f"Ethical VETO: Original action '{llm_decision_obj.action}' on component '{llm_decision_obj.component}' was vetoed. Confidence: {llm_decision_obj.confidence}. Original Reasoning: {llm_decision_obj.reasoning}",
                            confidence=0.0 # Veto sets confidence to 0
                        )
                    elif isinstance(ecm_review_result, KFMDecision): # Modified Decision
                        logger.warning(f"Ethical hook MODIFIED action from '{llm_decision_obj.action}' to '{ecm_review_result.action}' for component '{ecm_review_result.component}'.")
                        final_decision_obj = ecm_review_result
                    # If ecm_review_result is None, the original llm_decision_obj (now final_decision_obj) stands
                except Exception as e_ecm:
                    logger.error(f"Error during ethical post-planning review: {e_ecm}. Proceeding with LLM's original decision.")
                    # Fallback to LLM's decision if ECM fails
                    final_decision_obj = llm_decision_obj
            
            # --- Post-Decision Snapshot (if applicable) ---
            if self.snapshot_service and final_decision_obj.action in ["Fuck", "Kill"] and final_decision_obj.component:
                post_decision_snapshot_metadata = {
                    "stage": "post_decision_pre_execution",
                    "llm_decision_action": final_decision_obj.action,
                    "llm_decision_component": final_decision_obj.component,
                    "llm_decision_reasoning": final_decision_obj.reasoning,
                    "llm_decision_confidence": final_decision_obj.confidence,
                    "ethical_hook_applied": bool(ecm_review_result) 
                }
                component_state_for_snapshot = None
                if final_decision_obj.component:
                    component_state_for_snapshot = {
                        "target_component_id": final_decision_obj.component,
                        # In future, could fetch actual component state here if needed
                        "status_at_decision": "selected_for_action"
                    }
                
                logger.debug(f"KFMPlannerLlm: Taking post-decision snapshot for action {final_decision_obj.action}.")
                try:
                    await self.snapshot_service.take_snapshot(
                        trigger=f"post_decision_pre_execution_{final_decision_obj.action.lower()}", # Corrected: trigger_event to trigger
                        kfm_agent_state=current_kfm_agent_state_for_snapshot, # Agent state might have evolved or include new context
                        component_system_state=component_state_for_snapshot, # Pass component info here
                        additional_metadata=post_decision_snapshot_metadata # Corrected: metadata to additional_metadata
                    )
                except Exception as e_snap_post:
                    logger.error(f"KFMPlannerLlm: Error taking post-decision snapshot: {e_snap_post}")

            # If ethical hook modified the decision, log and use the modified one
            if ecm_review_result and ecm_review_result.action != final_decision_obj.action:
                logger.info(f"Ethical hook MODIFIED LLM decision. Original: {final_decision_obj.action} on {final_decision_obj.component}, New: {ecm_review_result.action} on {ecm_review_result.component}")
                final_decision_obj = ecm_review_result

            return final_decision_obj.to_dict()

        except KfmValidationError as ve:
            # ... existing error handling ...
            logger.error(f"KfmValidationError: {ve}. Raw LLM output: {ve.llm_output}")
            final_decision_obj = KFMDecision(action="Kill", component=None, reasoning=f"LLM output parsing error: {ve}", confidence=0.1, error=str(ve)).to_dict()
        except (APIError, RateLimitError, APITimeoutError, APIConnectionError, NetworkError, TimeoutException, APIStatusError) as http_err:
            # ... existing error handling ...
            logger.error(f"LLM API/Network Error: {http_err.__class__.__name__}: {http_err}")
            final_decision_obj = KFMDecision(action="Kill", component=None, reasoning=f"LLM API/Network Error: {http_err}", confidence=0.1, error=str(http_err)).to_dict()
        except Exception as e:
            # ... existing error handling ...
            logger.error(f"Unexpected error in KFM LLM decision process: {e}", exc_info=True)
            final_decision_obj = KFMDecision(action="Kill", component=None, reasoning=f"Unexpected error: {e}", confidence=0.1, error=str(e)).to_dict()

        return final_decision_obj

    def get_kfm_action(self, task_name: str, task_requirements: Dict[str, float], all_components_performance: Dict[str, Dict[str, float]], **kwargs) -> Dict[str, Any]:
        """Alias for decide_kfm_action for potential API compatibility needs.
        
        Ignores extra kwargs passed by some callers.
        """
        get_action_props = {
            "event_type": "get_kfm_action_alias_call",
            "task_name": task_name,
            "passed_kwargs_keys": list(kwargs.keys()) if kwargs else []
        }
        logger.info("get_kfm_action called (alias for decide_kfm_action).", extra={"props": get_action_props})
        return self.decide_kfm_action(task_name, task_requirements, all_components_performance) 