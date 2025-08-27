import asyncio

from browser_use import Agent, ChatOpenAI


async def main():
	task = 'Find the founders of browser-use'
	agent = Agent(task=task, llm=ChatOpenAI(model='gpt-4.1-mini'))
	await agent.run()


if __name__ == '__main__':
	asyncio.run(main())
