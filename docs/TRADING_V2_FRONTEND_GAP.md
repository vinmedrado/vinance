# Trading V2 — contrato para futura interface

O Trading V2 permanece um subsistema de pesquisa e **Paper Trading**. Ele não
possui rota ou item de navegação no frontend atual e não executa operações
reais.

Antes de qualquer exposição visual, ainda são necessários:

- API própria e versionada para os dados que a interface realmente consumirá;
- autenticação e autorização explícitas;
- contrato de produto que identifique permanentemente o modo `PAPER_ONLY`;
- experiência de simulação que não confunda resultados de pesquisa com capital
  disponível no Financial Autopilot;
- testes de integração, privacidade, risco e ausência de dispatch real.

Até esses gates existirem, o frontend não deve criar uma tela, rota ou chamada
de ação de Trading. Capital protegido, reserva, objetivos e o investment bucket
do Autopilot continuam isolados desse subsistema.
