# Analisador Inteligente de Loterias Caixa

App web em Streamlit que:

- Busca o **último resultado oficial** direto da API da Caixa (`servicebus2.caixa.gov.br`)
- Carrega o **histórico completo** dos sorteios (via dados abertos do repositório [eitchtee/loterias.json](https://github.com/eitchtee/loterias.json))
- Analisa frequência de números (quentes/frios)
- Calcula atrasos (números que há mais tempo não saem)
- Gera jogos sugeridos com base em estratégias estatísticas

## Loterias suportadas

- Mega-Sena
- Lotofácil
- Quina
- Lotomania
- Dia de Sorte

## Como executar

```bash
pip install -r requirements.txt
streamlit run app_loterias.py
```

## Aviso

Os sorteios são aleatórios. Análises de tendência **não aumentam** as chances reais de ganhar. Use apenas para entretenimento e curiosidade estatística. Jogue com responsabilidade.
