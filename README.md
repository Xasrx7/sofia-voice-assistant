# Sophia - Assistente de Voz em Python

A Sophia é uma assistente de voz que escuta comandos pelo microfone, envia a pergunta para a API do Google Gemini e responde em áudio em tempo real.

## O que ela faz

- Ouve comandos de voz: Transcreve a voz pelo microfone em tempo real.
- Processa com Inteligência Artificial: Envia o texto para a API do Google Gemini para responder dúvidas, explicar conteúdos ou manter uma conversa.
- Responde por áudio: Fala a resposta de volta através do sintetizador de voz.
- Funcionamento contínuo: Permite interagir por voz sem precisar de clicar em botões a cada frase.

## Tecnologias Utilizadas

- Python
- Google Gemini API
- SpeechRecognition (reconhecimento de voz)
- pyttsx3 (síntese de voz)

## Como Executar

1. Clone o repositório:
   git clone https://github.com/Xasrx7/sofia-voice-assistant.git

2. Instale as dependências:
   pip install speechrecognition pyttsx3 google-genai

3. Configure a sua chave da API do Gemini e execute:
   python sofia3.py

---
Desenvolvido por Pedro Barbosa.
