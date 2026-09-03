from __future__ import annotations

import random
import string

from python_pt_dictionary import dictionary


class WordService:
    def __init__(self, context):
        self.context = context
        self.alphabet = list(string.ascii_lowercase)

    @property
    def state(self):
        return self.context.state

    async def get_new_word(self) -> str:
        """Gera uma palavra e atualiza o estado volátil do bot."""
        new_word = None
        while new_word is None or not new_word:
            candidate = "".join(random.choice(self.alphabet) for _ in range(5))
            for _ in range(4):
                candidate = candidate.replace(random.choice(self.alphabet), "")
            new_word = dictionary.select(candidate, dictionary.Selector.PREFIX)

        selected = str.lower(new_word[random.randrange(len(new_word))].text)
        self.state.palavra_mute = selected
        print(f"Palavra foi trocada para: {selected}")
        return selected

    def clear(self) -> None:
        self.state.palavra_mute = None
        print("A palavra escolhida foi redefinida")

    def set_word(self, word: str) -> str:
        self.state.palavra_mute = word.lower()
        print(f"A palavra escolhida foi definida manualmente e agora é {self.state.palavra_mute}")
        return self.state.palavra_mute

    def set_message_limit(self, limit: int) -> None:
        self.state.palavras_max = limit

    def toggle_automatic_rotation(self) -> bool:
        self.state.troca_palavra = not self.state.troca_palavra
        return self.state.troca_palavra

    def contains_forbidden_word(self, content: str) -> bool:
        return bool(self.state.palavra_mute and self.state.palavra_mute in content.lower())

    def reset_message_counter(self) -> None:
        self.state.contador = 0

    def increment_message_counter(self) -> bool:
        self.state.contador += 1
        return self.state.troca_palavra and self.state.contador >= self.state.palavras_max

    def meaning(self, word: str):
        return dictionary.select(word.capitalize(), dictionary.Selector.PERFECT)

