"""Single source of truth for models available to the bot."""

MODEL_LIST = [
    "z-ai/glm-5.3-flash",
    "moonshotai/kimi-k3",
    "z-ai/glm-5.3",
    "deepseek-ai/deepseek-v4.1-flash"
]

DEFAULT_MODEL = "deepseek-ai/deepseek-v4.1-flash"
DEFAULT_FALLBACK_MODEL = "z-ai/glm-5.3"
