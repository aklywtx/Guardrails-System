# Reflection

Here are some of my observations, surprises, and learnings from building this guardrail system.

### What Worked Well

- **Embedding Similarity for Off-Topic:** I was surprised by how effective this was. It's fast, reliable for most clear-cut cases, and flexible—if we find it's failing on a certain topic, we can just add a new prototype to tune it without retraining a model.
- **Integrating a Real LLM (Ollama):** This was crucial for development. Using real LLM let me see where it actually failed.



### What Limitations or Gaps Remain?

I documented them in the `DESIGN.md`



### What I Would Add/Change with More Time

- **Test for Scale:** The first thing I'd do is test this on a much larger, more complex menu. The current sample menu is short, and I'm not confident the current regex-based `PriceValidator` will scale well when dish names start to overlap (e.g., "Beef Burger" vs. "Spicy Beef Burger").
- **Enforce Response Conciseness:** For a visually impaired user, listening to a long, chatty response is a waste of time. I would prioritize fixing the LLM's output length. This might mean a stricter prompt or forcing the LLM to give a structured output first, which would change how the entire guardrail system is designed.
- **Integrate Context More Deeply:** This is the most important one. Right now, only the `AllergenValidator` tracks context (the user's allergies). The `OffTopicDetector` is stateless, which is why it can get confused by short, contextual answers (like a user just saying "Yes"). 



### Interesting Surprises During Implementation

The biggest surprise was how much prompt engineering acted as its own guardrail. I changed the system prompt a few times, and before the last change, the model frequently gave wrong prices. After I adjusted the prompt to be more direct, it suddenly became very faithful.

This made me realize that a strong and preventive prompt can be a game-changer. Changing the LLM and prompts could have a quite huge effect on the guardrails design. I think maybe making guardrails more robust to the change of LLM side should also be considered when designing guardrails.



### Some Questions on Scalability

This project left me with a few open questions about scaling this system:

- How can I handle user requests for items not on the menu? Is that a hallucination to be blocked, or a valid request to be processed?
- Could the current guardrails still work if the menu becomes very long? What if the allergen information is not shown on the menu?
- At what point do the failures of the guardrails or the LLM become too complex for an automated response, and how can I design a human-in-the-loop fallback?
