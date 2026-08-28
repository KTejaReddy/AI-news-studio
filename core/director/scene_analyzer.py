"""Rules-based heuristic NLP text script analyzer for segmenting narration and planning storyboards.
"""

import re
from typing import List

from core.director.scene_plan import ScenePlan
from core.director.scene_timeline import SceneTimeline


class SceneAnalyzer:
    """Parses plain narration scripts, splits them into logical scenes, and plans visual details."""

    STOPWORDS = {
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "arent",
        "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "cant",
        "cannot", "could", "couldnt", "did", "didnt", "do", "does", "doesnt", "doing", "dont", "down", "during",
        "each", "few", "for", "from", "further", "had", "hadnt", "has", "hasnt", "have", "havent", "having",
        "he", "hed", "hell", "hes", "her", "here", "heres", "hers", "herself", "him", "himself", "his", "how",
        "hows", "i", "id", "ill", "im", "ive", "if", "in", "into", "is", "isnt", "it", "its", "itself", "lets",
        "me", "more", "most", "mustnt", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only",
        "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shant", "she", "shed",
        "shell", "shes", "should", "shouldnt", "so", "some", "such", "than", "that", "thats", "the", "their",
        "theirs", "them", "themselves", "then", "there", "theres", "these", "they", "theyd", "theyll", "theyre",
        "theyve", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasnt",
        "we", "wed", "well", "were", "weve", "werent", "what", "whats", "when", "whens", "where", "wheres",
        "which", "while", "who", "whos", "whom", "why", "whys", "with", "wont", "would", "wouldnt", "you",
        "youd", "youll", "youre", "youve", "your", "yours", "yourself", "yourselves", "this", "that", "with",
        "will", "shall", "just", "like"
    }

    def analyze_script(self, script_text: str) -> SceneTimeline:
        """Analyze narration text, divide into logical storyboard scenes, and return timeline.

        Args:
            script_text: Full voice-over narration text.

        Returns:
            A SceneTimeline object.
        """
        # 1. Clean script spacing
        text = " ".join(script_text.strip().split())
        if not text:
            return SceneTimeline()

        # 2. Sentence split by punctuation (. ! ?)
        # Using re.split with a capture group to keep the punctuation and optional quote marks
        parts = re.split(r"([.!?]['\"”’]?)\s+", text)
        sentences = []
        for i in range(0, len(parts) - 1, 2):
            sentences.append((parts[i] + parts[i+1]).strip())
        if len(parts) % 2 != 0 and parts[-1].strip():
            sentences.append(parts[-1].strip())

        scenes: List[ScenePlan] = []
        total_count = len(sentences)

        for idx, sentence in enumerate(sentences):
            scene_num = idx + 1
            
            # Estimate duration: average speaking rate ~150 words per minute (2.5 words per second)
            words = sentence.split()
            word_count = len(words)
            estimated_duration = max(3.0, round(word_count / 2.5, 1))

            # Determine scene type categorization
            scene_type = self._detect_scene_type(sentence, scene_num, total_count)

            # Heuristics based on scene types
            presenter_visibility = "Presenter"
            broll_keywords = self._extract_keywords(sentence)
            camera_shot = "Medium Shot"
            camera_movement = "Static"
            gesture_intensity = 1.0
            transition_type = "Cut"
            caption_style = "Standard Subtitles"
            background_music_mood = "Neutral"
            voice_emphasis = "Normal"
            emotion = "Neutral"

            if scene_type == "Hook":
                presenter_visibility = "Presenter"
                camera_shot = "Close-up"
                camera_movement = "Zoom In"
                gesture_intensity = 1.3
                background_music_mood = "Upbeat"
                voice_emphasis = "High"
                emotion = "Excited"
            elif scene_type == "Introduction":
                presenter_visibility = "Mixed"
                camera_shot = "Medium Shot"
                camera_movement = "Static"
                gesture_intensity = 1.1
                background_music_mood = "Neutral"
                emotion = "Warm"
            elif scene_type == "Statistic":
                presenter_visibility = "B-roll"
                camera_shot = "Wide Shot"
                camera_movement = "Pan Left"
                gesture_intensity = 0.5
                background_music_mood = "Serious"
                emotion = "Serious"
                transition_type = "Dissolve"
            elif scene_type == "Example":
                presenter_visibility = "B-roll"
                camera_shot = "Wide Shot"
                camera_movement = "Pan Right"
                gesture_intensity = 0.6
                background_music_mood = "Cinematic"
                emotion = "Neutral"
            elif scene_type == "Quote":
                presenter_visibility = "Presenter"
                camera_shot = "Close-up"
                camera_movement = "Static"
                gesture_intensity = 0.8
                voice_emphasis = "High"
                emotion = "Serious"
            elif scene_type == "CTA":
                presenter_visibility = "Presenter"
                camera_shot = "Medium Shot"
                camera_movement = "Zoom In"
                gesture_intensity = 1.5
                background_music_mood = "Energetic"
                voice_emphasis = "High"
                emotion = "Excited"
                caption_style = "Bold Centered"
            elif scene_type == "Ending":
                presenter_visibility = "Presenter"
                camera_shot = "Close-up"
                camera_movement = "Zoom Out"
                gesture_intensity = 1.2
                background_music_mood = "Inspirational"
                voice_emphasis = "High"
                emotion = "Happy"
            else:
                # Main points default
                presenter_visibility = "Mixed"
                camera_shot = "Medium Shot"
                camera_movement = "Static"
                gesture_intensity = 1.0

            scene = ScenePlan(
                scene_number=scene_num,
                scene_type=scene_type,
                duration=estimated_duration,
                narration=sentence,
                presenter_visibility=presenter_visibility,
                broll_keywords=broll_keywords,
                camera_shot=camera_shot,
                camera_movement=camera_movement,
                gesture_intensity=gesture_intensity,
                transition_type=transition_type,
                caption_style=caption_style,
                background_music_mood=background_music_mood,
                voice_emphasis=voice_emphasis,
                emotion=emotion
            )
            scenes.append(scene)

        return SceneTimeline(scenes=scenes)

    def _detect_scene_type(self, sentence: str, index: int, total: int) -> str:
        """Apply pattern matching rules to label the scene type."""
        text_lower = sentence.lower()

        if index == 1:
            return "Hook"

        # Look for Statistic patterns (percentages, quantities, figures)
        stat_regex = re.compile(r"\b\d+%|\b\d+\s*(percent|million|billion|trillion)\b")
        if stat_regex.search(text_lower):
            return "Statistic"

        if index == total:
            return "Ending"

        # Look for CTA patterns
        cta_keywords = ["subscribe", "click", "comment", "visit", "link below", "sign up", "follow us", "website"]
        if any(keyword in text_lower for keyword in cta_keywords):
            return "CTA"

        # Look for Quote patterns
        quote_regex = re.compile(r'["\'“”‘’]')
        if quote_regex.search(sentence):
            return "Quote"

        # Look for Example patterns
        example_keywords = ["for example", "such as", "for instance", "specifically", "illustrate", "case in point"]
        if any(keyword in text_lower for keyword in example_keywords):
            return "Example"

        if index == 2:
            return "Introduction"

        return "Main Point"

    def _extract_keywords(self, sentence: str) -> str:
        """Strip punctuation and stopwords to extract key descriptive terms."""
        # Strip special characters, convert to lower
        clean_text = re.sub(r"[^\w\s]", "", sentence.lower())
        words = clean_text.split()
        
        # Keep non-stopwords and filter duplicates
        keywords = []
        for word in words:
            if word not in self.STOPWORDS and word not in keywords:
                keywords.append(word)

        # Return top 4-5 words
        return ", ".join(keywords[:5])
