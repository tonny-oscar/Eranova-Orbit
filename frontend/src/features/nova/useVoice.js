import { useCallback, useEffect, useRef, useState } from 'react'

function recognitionClass() {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null
}

/**
 * Push-to-talk speech recognition. Nothing is captured until `start` is called
 * (the browser asks for microphone permission the first time) and capture stops
 * on `stop`. The transcript is returned for review; it is never sent automatically.
 */
export function useSpeechInput({ lang = 'en-KE', onFinal } = {}) {
  const Recognition = recognitionClass()
  const recognition = useRef(null)
  const finalText = useRef('')
  const onFinalRef = useRef(onFinal)
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    onFinalRef.current = onFinal
  }, [onFinal])

  const start = useCallback(() => {
    if (!Recognition || recognition.current) return
    const r = new Recognition()
    r.lang = lang
    r.interimResults = true
    r.continuous = true
    finalText.current = ''
    r.onresult = (event) => {
      let partial = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i]
        if (result.isFinal) finalText.current += result[0].transcript
        else partial += result[0].transcript
      }
      setInterim(`${finalText.current}${partial}`)
    }
    r.onerror = (event) => {
      setError(
        event.error === 'not-allowed'
          ? 'Microphone access was blocked. Allow it in your browser to use voice.'
          : 'Voice input stopped unexpectedly.',
      )
    }
    r.onend = () => {
      recognition.current = null
      setListening(false)
      setInterim('')
      const text = finalText.current.trim()
      if (text) onFinalRef.current?.(text)
    }
    setError(null)
    recognition.current = r
    setListening(true)
    r.start()
  }, [Recognition, lang])

  const stop = useCallback(() => recognition.current?.stop(), [])

  useEffect(() => () => recognition.current?.abort(), [])

  return { supported: Boolean(Recognition), listening, interim, error, start, stop }
}

export function useSpeechOutput() {
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const [speaking, setSpeaking] = useState(false)

  const speak = useCallback(
    (text) => {
      if (!supported || !text) return
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text.replace(/[•*_#`]/g, ''))
      utterance.onend = () => setSpeaking(false)
      utterance.onerror = () => setSpeaking(false)
      setSpeaking(true)
      window.speechSynthesis.speak(utterance)
    },
    [supported],
  )

  const cancel = useCallback(() => {
    if (supported) window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  useEffect(() => cancel, [cancel])

  return { supported, speaking, speak, cancel }
}
