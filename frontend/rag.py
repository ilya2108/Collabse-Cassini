import tiktoken
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler
from llama_index.core import Settings

from llama_index.llms.anthropic import Anthropic
from llama_index.llms.openai import OpenAI

from llama_index.core.query_pipeline import (
    QueryPipeline as QP,
    Link,
    InputComponent,
)
from llama_index.experimental.query_engine.pandas import (
    PandasInstructionParser,
)
from llama_index.core import Settings
from llama_index.core import PromptTemplate


class RAG:
    def __init__(
        self,
        df,
        model="openai",
    ) -> None:
        pass
        self.model = model
        if self.model == "openai":
            self.token_counter = TokenCountingHandler(
                tokenizer=tiktoken.encoding_for_model("gpt-3.5-turbo-0125").encode
            )
            Settings.llm = OpenAI(model="gpt-3.5-turbo-0125")
            Settings.callback_manager = CallbackManager([self.token_counter])

        if self.model == "anthropic":
            Settings.llm = Anthropic(model="claude-3-haiku-20240307")
        instruction_str = (
            "1. Convert the query to executable Python code using Pandas.\n"
            "2. The final line of code should be a Python expression that can be called with the `eval()` function.\n"
            "3. The code should represent a solution to the query.\n"
            "4. PRINT ONLY THE EXPRESSION.\n"
            "5. Do not quote the expression.\n"
        )

        pandas_prompt_str = (
            "You are working with a pandas dataframe in Python.\n"
            "The name of the dataframe is `df`.\n"
            "This is the result of `print(df.head())`:\n"
            "{df_str}\n\n"
            "Here is the result of `print(df.columns)`:\n"
            "{df_col_str}\n\n"
            "Follow these instructions:\n"
            "{instruction_str}\n"
            "Query: {query_str}\n\n"
            "Expression:"
        )

        response_synthesis_prompt_str = (
            "Given an input question, synthesize a response from the query results. Output the response in Russian language."
            "Query: {query_str}\n\n"
            "Pandas Instructions (optional):\n{pandas_instructions}\n\n"
            "Pandas Output: {pandas_output}\n\n"
            "Response: "
        )

        pandas_prompt = PromptTemplate(pandas_prompt_str).partial_format(
            instruction_str=instruction_str,
            df_str=df.head(5),
            df_col_str=df.columns,
        )
        pandas_output_parser = PandasInstructionParser(df)
        response_synthesis_prompt = PromptTemplate(response_synthesis_prompt_str)
        self.qp = QP(
            modules={
                "input": InputComponent(),
                "pandas_prompt": pandas_prompt,
                "llm1": Settings.llm,
                "pandas_output_parser": pandas_output_parser,
                "response_synthesis_prompt": response_synthesis_prompt,
                "llm2": Settings.llm,
            },
            verbose=True,
        )
        self.qp.add_chain(["input", "pandas_prompt", "llm1", "pandas_output_parser"])
        self.qp.add_links(
            [
                Link("input", "response_synthesis_prompt", dest_key="query_str"),
                Link(
                    "llm1", "response_synthesis_prompt", dest_key="pandas_instructions"
                ),
                Link(
                    "pandas_output_parser",
                    "response_synthesis_prompt",
                    dest_key="pandas_output",
                ),
            ]
        )
        # add link from response synthesis prompt to llm2
        self.qp.add_link("response_synthesis_prompt", "llm2")

    def answer_question(self, question: str):
        response = self.qp.run(
            query_str=question,
        )
        if self.model == "openai":
            print(
                "Embedding Tokens: ",
                self.token_counter.total_embedding_token_count,
                "\n",
                "LLM Prompt Tokens: ",
                self.token_counter.prompt_llm_token_count,
                "\n",
                "LLM Completion Tokens: ",
                self.token_counter.completion_llm_token_count,
                "\n",
                "Total LLM Token Count: ",
                self.token_counter.total_llm_token_count,
                "\n",
            )
        return response