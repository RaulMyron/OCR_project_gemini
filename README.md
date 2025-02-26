# OCR_project_gemini
# Trabalho IST OCR

Este jupyter notebook tem por objetivo auxiliar a entidade DACES-UNB,no intuito de acelerar processos internos de SCAN OCR de maneira mais inteligente, garantindo precisão e menos trabalho físico para o processo de scan de livros, facilitando a vida da equipe DACES.

Para poder rodar é necessário uma key do gemini, que pode ser gerada gratuitamente aqui: https://aistudio.google.com/app/apikey

Para rodar sem jupyter lab, clique [aqiui: Rodar sem Jupyter ou vá para a última sessão](#apenas-python3-sem-jupyter)

# Jupyter lab set up

Para criação, primeiramente crie um enviroment python:

```shell
python3 -m venv jupyter_env #no ubuntu
source jupyter_env/bin/activate #para ativar enviroment
pip install jupyter notebook
pip install -r requirements.txt
jupyte lab #para rodar
```

Caso ao rodar não consiga abrir, tente abrir o link http://127.0.0.1:8888/lab

Para apenas rodar 
```shell
source jupyter_env/bin/activate #para ativar enviroment
jupyte lab #para rodar
```
Para rodar dentro do cedula, clique no botão de play ou shift + enter

# Apenas python3 sem jupyter

Para isto, é necessário:

```shell
python3 -m venv jupyter_env #no ubuntu
pip install -r requirements.txt
python3 main.py
```

Lembre de substituir as variaveis caminho_arquivo.pdf e apikey para seus valores.