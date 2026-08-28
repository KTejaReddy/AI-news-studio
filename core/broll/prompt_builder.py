"""Builder to synthesize detailed descriptive prompts and recommend asset types for B-roll generation.
"""

from core.director.scene_plan import ScenePlan


class PromptBuilder:
    """Consumes Director ScenePlans and constructs detailed prompts for diffusion models."""

    @staticmethod
    def build_prompt_and_type(scene: ScenePlan) -> tuple[str, str]:
        """Analyze scene plan settings and synthesize a text prompt and target asset type.

        Args:
            scene: ScenePlan context object.

        Returns:
            Tuple of (prompt_string, asset_type_string).
        """
        # 1. Recommend asset type based on Scene Type
        st = scene.scene_type.lower()
        if "statistic" in st:
            asset_type = "Motion Graphic"
        elif "cta" in st:
            asset_type = "Animation"
        elif "example" in st:
            asset_type = "Stock Footage"
        elif "quote" in st:
            asset_type = "Image"
        else:
            asset_type = "Video"

        # 2. Extract key components from scene settings
        keywords = scene.broll_keywords.strip()
        if not keywords:
            # Fallback keywords if empty
            keywords = "cinematic view"

        emotion = scene.emotion or "Neutral"
        shot = scene.camera_shot or "Medium Shot"
        movement = scene.camera_movement or "Static"

        # 3. Construct prompt description
        base_desc = f"Cinematic 4K, high visual fidelity. Visual description of: {keywords}."
        style_notes = f"Mood/tone: {emotion}, shot framing: {shot}, camera action: {movement}."
        
        if asset_type == "Motion Graphic":
            prompt = (
                f"Minimalist clean infographic animation overlay. "
                f"Displaying statistical data mapping to: {scene.narration[:60]}... "
                f"Flat vector design, corporate colors, smooth motion design, loopable."
            )
        elif asset_type == "Animation":
            prompt = (
                f"Modern 2D/3D visual animation. "
                f"Displaying action prompt for: {keywords}. "
                f"Vibrant colors, call-to-action indicators, clean keyframe styling."
            )
        elif asset_type == "Image":
            prompt = f"Fine-art photography, high detail. {base_desc} Style: dramatic studio lighting."
        else:
            # Video / Stock Footage default
            prompt = f"Cinematic footage, photorealistic. {base_desc} {style_notes} Ambient lighting."

        return prompt, asset_type
