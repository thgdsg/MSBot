import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.services import writing_style
from app.services.memory_service import MemoryService


class WritingStyleTests(unittest.IsolatedAsyncioTestCase):
    async def test_persistence_prompt_and_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            context = SimpleNamespace(config=SimpleNamespace(path=lambda name: Path(directory) / name))
            memory = MemoryService(context)
            self.assertEqual(await memory.review_writing_style('ah, primeira resposta'), 'ah, primeira resposta')
            await memory.review_writing_style('AH! segunda resposta')
            self.assertEqual(await memory.review_writing_style('ah, terceira resposta'), 'terceira resposta')
            reloaded = MemoryService(context)
            prompt = reloaded.text_for_prompt(channel_id='1', user_id='2')
            self.assertIn('WritingStyle', prompt)
            self.assertIn("'ah,'", prompt)
            self.assertEqual(await reloaded.review_writing_style('ah, quarta resposta'), 'quarta resposta')
            self.assertTrue(list((Path(directory) / 'memory_backups').glob('*.md')))

    def test_window_forgets_old_habits_and_preserves_content(self):
        state = {}
        for _ in range(3):
            writing_style.observe(state, 'a resposta correta depende do contexto')
        self.assertTrue(state['habits'])
        text = 'a resposta correta depende do contexto'
        self.assertEqual(writing_style.suppress_filler(text, state), text)
        for _ in range(20):
            writing_style.observe(state, '```python\nprint(1)\n```')
        self.assertFalse(state['habits'])
        self.assertEqual(len(state['recent']), 20)

    def test_quotes_are_not_counted_and_empty_remainder_is_preserved(self):
        self.assertEqual(writing_style.opening('> ah, citado'), '')
        state = {}
        for _ in range(3):
            writing_style.observe(state, 'ah,')
        self.assertEqual(writing_style.suppress_filler('ah,', state), 'ah,')
