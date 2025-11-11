from typing import List, Literal, Union, Tuple, Optional
import numpy as np
from sentence_transformers import SentenceTransformer, util
import time

THRESHOLD_CLARIFY=0.48
THRESHOLD_OFFTOPIC=0.4

# Prototype queries that represent on-topic interactions
ON_TOPIC_PROTOTYPES = [
    # Menu inquiry
    "What dishes are on the menu?",
    "Show me the menu.",
    "What kind of food is available here?",
    "What do you have?",
    
    # Recommendation
    "Can you recommend something to eat?",
    "What's the most popular item?",
    "Help me choose what to order.",
    "What would you recommend?",
    "I need help ordering.",
    
    # Price
    "How much is the pasta?",
    "Which dishes are under ten dollars?",
    "What's the cheapest dish?",
    "How much does that cost?",
    
    # Allergy
    "I'm allergic to peanuts.",
    "Which dishes are nut-free?",
    "Is this gluten-free?",
    "Does this contain dairy?",
    
    # Dietary preferences
    "I'm vegetarian.",
    "Show me something spicy.",
    "Give me something not too spicy.",
    "Do you have vegan options?",
    
    # Comparison
    "Which is better, the beef burger or the chicken burger?",
    "Compare the spicy tofu and the mild one.",
    
    # Order management and confirmation
    "I want the pizza.",
    "I'll take that.",
    "That sounds great.",
    "I'd like to order.",
    "Can I get the burger?",
]

class OffTopicDetector:
    """
    Off-topic detection using embedding similarity.
    Compares user input against prototype on-topic queries.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        threshold_offtopic: float=THRESHOLD_OFFTOPIC,
        threshold_clarify: float=THRESHOLD_CLARIFY,
        prototypes: Optional[List[str]]=None
    ):

        print(f"Loading off-topic detection model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        self.threshold_offtopic = threshold_offtopic
        self.threshold_clarify = threshold_clarify

        # Use provided prototypes or defaults
        self.prototypes = prototypes or ON_TOPIC_PROTOTYPES

        # Precompute prototype embeddings for efficiency
        self.prototype_embeddings = self.model.encode(
            self.prototypes,
            convert_to_tensor=True,
            normalize_embeddings=True
        )
        print("Off-topic detector ready.")

    def detect(self, text: str) -> Literal["off_topic", "clarify", "on_topic"]:
        """
        Detect if the input text is off-topic based on similarity thresholds.
        Returns just the status string for simpler integration.
        """
        # 1. Encode user input
        embedding = self.model.encode(text, convert_to_tensor=True, normalize_embeddings=True)

        # 2. Calculate cosine similarities with all prototypes
        cosine_scores = util.cos_sim(embedding, self.prototype_embeddings)[0]

        # 3. Find the maximum similarity score (best match)
        max_score = float(np.max(cosine_scores.cpu().numpy()))

        # 4. Compare against thresholds
        if max_score < self.threshold_offtopic:
            return "off_topic", max_score
        elif max_score < self.threshold_clarify:
            return "clarify", max_score
        else:
            return "on_topic", max_score


# Convenience function for one-off detections
_default_detector = None

def detect_offtopic(text: str) -> Literal["off_topic", "clarify", "on_topic"]:
    """
    Convenience function for off-topic detection without instantiating a detector.
    Uses a singleton detector instance.
    """
    global _default_detector
    if _default_detector is None:
        _default_detector = OffTopicDetector()

    result, _ = _default_detector.detect(text)
    return result
