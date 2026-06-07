import re


class Transliterator:
    def __init__(self):
        self._ko = None
        self._ja = None
        self._any = None

    def _init_ko(self):
        if self._ko is None:
            try:
                from hangul_romanize import Transliter as KoRomanizer
                from hangul_romanize.rule import academic as default_rules
                self._ko = KoRomanizer(default_rules)
            except Exception:
                self._ko = False

    def _init_ja(self):
        if self._ja is None:
            try:
                import pykakasi
                self._ja = pykakasi.kakasi()
            except Exception:
                self._ja = False

    def _init_any(self):
        if self._any is None:
            try:
                from anyascii import anyascii
                self._any = anyascii
            except Exception:
                self._any = False

    def to_romaji(self, text, lang):
        if lang == 'ko':
            self._init_ko()
            if self._ko:
                return self._ko.translit(text)
        elif lang == 'ja':
            self._init_ja()
            if self._ja:
                return ' '.join(r['hepburn'] for r in self._ja.convert(text))
        self._init_any()
        if self._any:
            return self._any(text)
        return text

    def transliterate_file(self, srt_path, lang):
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        blocks = re.split(r'\n\s*\n', content.strip())
        new_blocks = []
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                new_blocks.append(block)
                continue
            time_line = lines[1]
            text_lines = lines[2:]
            new_lines = []
            for ln in text_lines:
                rom = self.to_romaji(ln, lang)
                if rom and rom != ln:
                    new_lines.append(rom)
                else:
                    new_lines.append(ln)
            new_blocks.append(f"{lines[0]}\n{time_line}\n" + '\n'.join(new_lines))
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(new_blocks) + '\n')
        return srt_path