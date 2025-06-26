# fung-eye-backend-llm-server
Backend LLM Server for [FungEye](https://github.com/duatonic/fung-eye.git).

To run the server, run this command to install the requirements.
```
pip install Flask ollama
```

Next, make sure you have ollama installed and then run this command to pull the LLM model (you can use any model you want as long as it has the ability to take image as input).

```
ollama pull gemma3:4b-it-qat
```

Finally, run ollama then run the server by running the script.
```
ollama serve
```

```
python app.py
```
