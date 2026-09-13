# Token Usage and Cost Analysis

Model usage behind the shipped `output.csv`: evidence generation (message/image/salary passes) plus the final full-dataset run, which replayed the evidence cache.

| model | provider | calls | input tokens | output tokens | est. cost (USD) |
|---|---|---|---|---|---|
| google/gemma-4-31b-it:free | openai-compat | 1 | 113 | 201 | $0.0007 |
| inclusionai/ling-3.0-flash-vl:free | openai-compat | 16 | 19678 | 10897 | $0.0000 |
| nex-agi/nex-n2.5-mini:free | openai-compat | 67 | 44542 | 285732 | $0.0000 |
| nvidia/nemotron-3.5-lightning:free | openai-compat | 2 | 2478 | 34248 | $0.0000 |
| poolside/laguna-s-2.1:free | openai-compat | 3 | 695 | 136 | $0.0011 |
| **overall** |  | 89 | 67506 | 331214 | $0.0018 |

- Average tokens per request: 1595 (input 270 / output 1325)
- Estimated cost per request: $0.00001
