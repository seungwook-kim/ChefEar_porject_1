"""상시 마이크용 실시간 VAD(음성구간감지) 세그먼터 - 2026-08-20 추가.

streamlit-webrtc가 브라우저 마이크에서 실시간으로 오디오 프레임을 넘겨주는데,
그건 그냥 끊김 없이 이어지는 오디오 스트림일 뿐이다("다음"이라는 한 마디가
어디서 시작해서 어디서 끝나는지는 모른다). 이 파일의 MicVadSegmenter가 그
프레임들을 하나씩 받아서, silero-vad로 "지금 말하고 있다/조용하다"를 판단하고,
"말하다가 min_silence_duration_ms만큼 조용해지면 거기까지가 한 발화"라고
잘라서 오디오 배열 하나로 돌려준다. 그 결과를 stt.infer.stt_transcribe()에
넣으면 텍스트가 되고, 그 텍스트를 orchestration.pipeline.handle_utterance()에
넣으면 텍스트 테스트 화면과 똑같은 파이프라인을 탄다.
"""
from __future__ import annotations

import numpy as np


class MicVadSegmenter:
    """오디오 프레임을 계속 넣어주면(feed), 발화 하나가 끝날 때마다 그 구간의
    16kHz 모노 float32 오디오 배열을 돌려준다. 아직 발화 중이거나 무음이면 None.
    """

    CHUNK_SAMPLES = 512  # silero-vad가 16kHz에서 요구하는 고정 청크 크기(32ms)

    def __init__(self, min_silence_duration_ms: int = 600, threshold: float = 0.5):
        from silero_vad import VADIterator, load_silero_vad

        self._iterator = VADIterator(
            load_silero_vad(),
            threshold=threshold,
            sampling_rate=16000,
            # 사람이 문장 사이에 숨 쉬는 정도의 짧은 멈춤(수백ms)까지 "발화 끝"으로
            # 잘라버리면 "다음"처럼 짧은 단어는 괜찮아도 긴 문장이 중간에 끊길 수
            # 있다. 600ms면 자연스러운 문장 내 쉼은 넘기고, 진짜 "말 다 끝남"만
            # 잡아내는 편(값 자체는 실측 튜닝 전 임시값, intent_classifier.THRESHOLD와
            # 같은 성격).
            min_silence_duration_ms=min_silence_duration_ms,
        )
        self._pending = np.zeros(0, dtype=np.float32)  # 아직 512개 안 채워진 나머지
        self._speech_chunks: list[np.ndarray] = []
        self._in_speech = False

    def reset(self) -> None:
        self._iterator.reset_states()
        self._pending = np.zeros(0, dtype=np.float32)
        self._speech_chunks = []
        self._in_speech = False

    def feed(self, samples: np.ndarray, sample_rate: int) -> np.ndarray | None:
        """samples: 임의의 sample_rate/모양(모노 또는 다채널, int16 또는 float)의
        오디오 조각 하나. 이번 호출로 발화 하나가 완성됐으면 그 오디오(16kHz
        모노 float32)를 반환하고, 아니면 None을 반환한다.
        """
        mono16k = self._to_mono_16k_float32(samples, sample_rate)
        self._pending = np.concatenate([self._pending, mono16k])

        result = None
        while len(self._pending) >= self.CHUNK_SAMPLES:
            chunk = self._pending[: self.CHUNK_SAMPLES]
            self._pending = self._pending[self.CHUNK_SAMPLES :]

            event = self._iterator(chunk)

            if event is not None and "start" in event:
                self._in_speech = True
                self._speech_chunks = [chunk]
            elif self._in_speech:
                # "end" 신호가 이번 청크에서 나오더라도, 이 청크 자체는 아직
                # 발화의 일부(문장 끝자락)이므로 먼저 담아둔다.
                self._speech_chunks.append(chunk)

            if event is not None and "end" in event:
                self._in_speech = False
                if self._speech_chunks:
                    result = np.concatenate(self._speech_chunks)
                self._speech_chunks = []

        return result

    @staticmethod
    def _to_mono_16k_float32(samples: np.ndarray, sample_rate: int) -> np.ndarray:
        samples = np.asarray(samples)
        if np.issubdtype(samples.dtype, np.integer):
            # int16 PCM(webrtc/av 기본 포맷) -> [-1, 1] float32
            samples = samples.astype(np.float32) / 32768.0
        else:
            samples = samples.astype(np.float32)

        if samples.ndim > 1:
            # av.AudioFrame.to_ndarray()는 보통 (채널, 샘플) 모양으로 준다 -
            # 어느 축이 채널인지 확실치 않을 수 있어 더 작은 축을 채널로 보고 평균낸다.
            channel_axis = 0 if samples.shape[0] < samples.shape[1] else 1
            samples = samples.mean(axis=channel_axis)

        if sample_rate != 16000:
            import librosa

            samples = librosa.resample(samples, orig_sr=sample_rate, target_sr=16000)

        return samples
