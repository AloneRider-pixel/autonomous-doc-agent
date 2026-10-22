"""Run both required test inputs end-to-end and print the plan + execution trace.

Usage:  python demo.py            (uses the best available provider)
        AGENT_LLM=mock python demo.py   (force the offline fallback)
"""
from app.agent import Agent

STANDARD_REQUEST = (
    "Create a project plan for migrating our internal company wiki to a new "
    "platform over 6 weeks."
)
COMPLEX_REQUEST = (
    "Prepare something for the board about the Q3 product thing - we may need "
    "budget numbers but Finance has not confirmed them, keep it short but make "
    "sure it covers everything, and we might present it Tuesday or maybe next month."
)

if __name__ == "__main__":
    agent = Agent()
    for label, req in [("STANDARD", STANDARD_REQUEST), ("COMPLEX", COMPLEX_REQUEST)]:
        print("=" * 78)
        print(f"[{label}] {req}")
        result = agent.run(req)
        print(f"provider   : {result['provider']}")
        print(f"doc_type   : {result['doc_type']}")
        print(f"title      : {result['title']}")
        print(f"assumptions: {result['assumptions']}")
        print("plan tasks :")
        for t in result["plan"]["tasks"]:
            print(f"  {t['id']}. [{t['kind']}] {t['title']} - {t['detail']}")
        print("execution trace:")
        for s in result["steps"]:
            print(f"  {s['t']:>6}s  {s['event']}")
        print(f"document   : {result['document_path']}")
