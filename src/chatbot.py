"""
Restaurant ordering chatbot with guardrails for visually impaired users.

This chatbot demonstrates the integration of guardrails into a local LLM via Ollama.
"""

from typing import Optional, Dict, Any, List
import json
import uuid
import ollama

from src.guardrails.manager import GuardrailManager
from src.guardrails.output.base import ErrorSeverity
from src.menu_data import SAMPLE_MENU


class RestaurantChatbot:
    """
    Restaurant ordering chatbot with modular guardrails and Ollama LLM integration.
    """

    def __init__(
        self,
        menu: Optional[Dict] = None,
        model: str = "llama3.2",
        ollama_host: Optional[str] = None
    ):
        """
        Initialize the chatbot with GuardrailManager.
        """

        self.menu = menu or SAMPLE_MENU
        self.model = model
        self.guardrails = GuardrailManager(self.menu)
        self.current_session_id = str(uuid.uuid4()) # Session management for stateful guardrails
        self.conversation_history = []
        self.llm_messages = []
        self.system_prompt = self._create_system_prompt()

        if ollama_host:
            self.client = ollama.Client(host=ollama_host)
        else:
            self.client = ollama

    def _create_system_prompt(self) -> str:
        """
        Create system prompt with menu information.
        """
        
        return f"""
        You are a helpful restaurant ordering assistant designed for visually impaired users. 
        You help users browse the menu, understand dishes, check prices, handle dietary restrictions, and place orders.

        {self.menu}
        
        IMPORTANT INSTRUCTIONS:
        1. ONLY provide information from the menu above. Never make up dishes, prices, or allergen information.
        2. If asked about a dish not on the menu, clearly state it's not available.
        3. Be precise about prices - use the exact prices from the menu.
        4. Take allergies and dietary restrictions VERY seriously - always provide accurate allergen information.
        5. Be conversational and friendly, but prioritize accuracy over creativity.

        ACCESSIBILITY REQUIREMENTS (CRITICAL - users will hear responses):
        6. Keep responses SHORT - 1-3 sentences preferred.
        7. Put the MOST IMPORTANT information FIRST (price, allergens, availability).
        8. Use SIMPLE, DIRECT language - avoid elaborate descriptions.
        9. For yes/no questions, answer directly first, then explain briefly if needed.

        Your goal is to help users confidently order food that meets their needs QUICKLY and CLEARLY.
        """

    def process_query(self, user_input: str, skip_guardrails: bool = False) -> Dict[str, Any]:
        """
        Process query using GuardrailManager.
        """
        result = {
            "response": "",
            "guardrail_result": None,
            "similarity_score": 0.0,
            "blocked": False,
            "llm_used": False,
            "validation_result": None,
            "validation_errors": []
        }

        # --- 1. Input Guardrails ---
        if not skip_guardrails:
            input_result = self.guardrails.check_input(user_input, self.current_session_id)
            
            # Map new result format to old keys for compatibility with your demo loop
            result["guardrail_result"] = input_result.topic_status
            result["similarity_score"] = input_result.similarity_score
            
            if input_result.is_blocked:
                result["blocked"] = True
                if input_result.topic_status == "off_topic":
                    result["response"] = self._handle_offtopic()
                else:
                    result["response"] = f"I cannot process that request: {input_result.block_reason}"
                
                self._log_history(user_input, input_result.topic_status)
                return result
                
            elif input_result.topic_status == "clarify":
                result["response"] = self._handle_clarification()
                self._log_history(user_input, "clarify")
                return result

        # --- 2. LLM Generation ---
        try:
            llm_response = self._get_llm_response(user_input)
            result["llm_used"] = True

            # --- 3. Output Guardrails (Managed by GuardrailManager) ---
            if not skip_guardrails:
                # This now includes Allergen checks using session state!
                validation = self.guardrails.check_output(llm_response, self.current_session_id)
                
                result["validation_result"] = validation
                result["validation_errors"] = validation.errors

                if validation.critical_errors:
                    # CRITICAL: Block immediately (e.g., unsafe allergen recommendation)
                    result["response"] = self._handle_critical_validation_error(validation, llm_response)
                    result["blocked"] = True
                elif not validation.is_valid:
                    # HIGH/MEDIUM: Try to auto-correct (e.g., wrong prices)
                    corrected_response = self._try_correct_response(llm_response, validation)
                    if corrected_response:
                         result["response"] = corrected_response
                         # Optionally mark that it was auto-corrected
                    else:
                         # Could not auto-correct a high severity error -> block
                         result["response"] = self._handle_validation_error(validation)
                         result["blocked"] = True
                else:
                    result["response"] = llm_response
            else:
                result["response"] = llm_response

        except Exception as e:
            result["response"] = f"Error processing request: {str(e)}. Please try again."
            result["llm_used"] = False

        if not result["blocked"]:
             self._log_history(user_input, "on_topic" if not skip_guardrails else "skipped")

        return result

    def _log_history(self, user_input, status):
        """Helper to log history for stats."""
        self.conversation_history.append({
            "user": user_input,
            "guardrail": status
        })

    def _get_llm_response(self, user_input: str) -> str:
        self.llm_messages.append({"role": "user", "content": user_input})
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "system", "content": self.system_prompt}, *self.llm_messages]
        )
        assistant_message = response['message']['content']
        self.llm_messages.append({"role": "assistant", "content": assistant_message})
        return assistant_message

    def _handle_offtopic(self) -> str:
        return ("I'm sorry, but I can only help you with menu ordering and food-related questions. "
                "How can I help you with the menu today?")

    def _handle_clarification(self) -> str:
         return "Could you please be more specific about what you'd like to order or know about the menu?"

    def _handle_critical_validation_error(self, validation, llm_response) -> str:
        # Updated to use new validation structure
        error_msgs = [f"⚠️ SAFETY WARNING: {e.message}" for e in validation.critical_errors]
        return ("I apologize, but I need to verify my information for your safety.\n" + 
                "\n".join(error_msgs) + 
                "\n I am sorry, but your ordering contains a known allergen. Please let me try again. What would you like to know?")

    def _handle_validation_error(self, validation) -> str:
        return ("I apologize, but I'm not confident in the accuracy of my response regarding prices or details. "
                "Please let me double-check the menu.")

    def _try_correct_response(self, llm_response: str, validation) -> Optional[str]:
        """
        Updated auto-correction using the new '.corrected_text' field.
        """
        corrected = llm_response
        fixed_something = False
        
        for error in validation.errors:
            # Only apply fixes if explicitly provided by the validator
            if error.original_text and error.corrected_text:
                corrected = corrected.replace(error.original_text, error.corrected_text)
                fixed_something = True
        
        return corrected if fixed_something else None

    def get_conversation_summary(self) -> Dict[str, Any]:
        # (Kept exactly as before)
        total = len(self.conversation_history)
        if total == 0: return {"total_queries": 0}
        on_topic = sum(1 for msg in self.conversation_history if msg["guardrail"] == "on_topic")
        off_topic = sum(1 for msg in self.conversation_history if msg["guardrail"] == "off_topic")
        clarify = sum(1 for msg in self.conversation_history if msg["guardrail"] == "clarify")
        return {
            "total_queries": total, "on_topic": on_topic, "off_topic": off_topic, "clarify": clarify,
            "on_topic_rate": on_topic/total, "off_topic_rate": off_topic/total
        }

    def reset_conversation(self):
        self.conversation_history = []
        self.llm_messages = []
        # Also reset session state in guardrails!
        self.guardrails.reset_session(self.current_session_id)
        self.current_session_id = str(uuid.uuid4())


def demo_chatbot():
    """
    Demo function to show chatbot in action.

    Run with: python -m src.chatbot
    Or with baseline mode: python -m src.chatbot --baseline
    """
    import sys

    # Check for baseline mode flag
    baseline_mode = "--baseline" in sys.argv or "--no-guardrails" in sys.argv

    print("="*80)
    print("RESTAURANT ORDERING ASSISTANT FOR VISUALLY IMPAIRED USERS")
    print("="*80)

    if baseline_mode:
        print("\n⚠️  BASELINE MODE: Guardrails DISABLED")
        print("This mode shows raw LLM responses without any validation.")
        print("Use this to compare against guardrails-enabled mode.\n")
    else:
        print("\n🛡️  GUARDRAILS ENABLED")
        print("Input and output guardrails are active for safety.")
        print("Run with --baseline to see raw LLM without guardrails.\n")

    print("This chatbot uses Ollama for natural language understanding.")
    print("Make sure Ollama is running: ollama serve")
    print("\nCommands:")
    print("  'quit' - Exit the chatbot")
    print("  'stats' - Show conversation statistics")
    print("  'reset' - Start a new conversation")
    if not baseline_mode:
        print("  'toggle' - Switch to baseline mode")
    else:
        print("  'toggle' - Switch to guardrails mode")
    print()

    try:
        chatbot = RestaurantChatbot()
        print(f"✓ Connected to Ollama (model: {chatbot.model})")
    except Exception as e:
        print(f"✗ Error connecting to Ollama: {e}")
        print("\nMake sure:")
        print("  1. Ollama is installed: https://ollama.ai")
        print("  2. Ollama is running: ollama serve")
        print("  3. Model is pulled: ollama pull llama3.2")
        return

    skip_guardrails = baseline_mode

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() in ["quit", "exit", "q"]:
            print("\nThank you for using the restaurant assistant!")
            stats = chatbot.get_conversation_summary()
            if stats.get('total_queries', 0) > 0:
                print("\nConversation Summary:")
                print(f"  Total queries: {stats.get('total_queries', 0)}")
                print(f"  On-topic: {stats.get('on_topic', 0)}")
                print(f"  Clarifications: {stats.get('clarify', 0)}")
                print(f"  Off-topic: {stats.get('off_topic', 0)}")
            break

        if user_input.lower() == "stats":
            stats = chatbot.get_conversation_summary()
            print("\nConversation Statistics:")
            print(f"  Total queries: {stats.get('total_queries', 0)}")
            if stats.get('total_queries', 0) > 0:
                print(f"  On-topic rate: {stats.get('on_topic_rate', 0):.1%}")
                print(f"  Clarification rate: {stats.get('clarify_rate', 0):.1%}")
                print(f"  Off-topic rate: {stats.get('off_topic_rate', 0):.1%}")
            continue

        if user_input.lower() == "reset":
            chatbot.reset_conversation()
            print("\n✓ Conversation reset")
            continue

        if user_input.lower() == "toggle":
            skip_guardrails = not skip_guardrails
            mode = "BASELINE (no guardrails)" if skip_guardrails else "GUARDRAILS ENABLED"
            print(f"\n✓ Switched to: {mode}")
            continue

        if not user_input:
            continue

        # Process query
        mode_indicator = "[BASELINE]" if skip_guardrails else "[GUARDRAILS]"
        print(f"\n{mode_indicator} Processing...")
        result = chatbot.process_query(user_input, skip_guardrails=skip_guardrails)

        # Display response with guardrail info
        if not skip_guardrails:
            guardrail_info = []
            if result.get('guardrail_result'):
                guardrail_info.append(f"Input: {result['guardrail_result']}")
                guardrail_info.append(f"Similarity: {result['similarity_score']:.3f}")

            if result.get('validation_errors'):
                num_errors = len(result['validation_errors'])
                guardrail_info.append(f"Output Validation: {num_errors} error(s)")

            guardrail_info.append(f"Blocked: {result['blocked']}")
            guardrail_info.append(f"LLM Used: {result['llm_used']}")

            print(f"[{', '.join(guardrail_info)}]")

            # Show validation errors if any
            if result.get('validation_errors'):
                print("\n⚠️  Validation Errors Detected:")
                for error in result['validation_errors']:
                    print(f"  [{error.severity.value.upper()}] {error.message}")
                print()
        else:
            # Baseline mode - just show that it's raw LLM
            print(f"[Raw LLM Response - No Guardrails]")

        print(f"\nAssistant: {result['response']}")


if __name__ == "__main__":
    demo_chatbot()
