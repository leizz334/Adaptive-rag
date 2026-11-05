from app.agents.nodes.faithfulness import faithfulness_node
from app.agents.nodes.generate import generate_node
from app.core.enums import RetrievalStrategy
from app.guardrails.hallucination import FaithfulnessChecker
from app.providers.base import LLMResponse


async def test_model_refused_flag_does_not_bypass_answer_validation():
    class Model:
        async def generate(self, *args, **kwargs):
            return LLMResponse('{"answer":"订单ORD7070已取消，退款成功。","refused":true}')

    llm = Model()
    state = dict(
        user_query="ORD7070取消条件是什么", strategy=RetrievalStrategy.AGENT, tool_results=[]
    )
    generated = await generate_node(state, llm)
    result = await faithfulness_node({**state, **generated}, FaithfulnessChecker(llm), llm)
    answer = result.get("final_answer", generated["final_answer"])
    assert "已取消" not in answer and "退款成功" not in answer
