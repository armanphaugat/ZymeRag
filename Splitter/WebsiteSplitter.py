from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
class WebsiteTextSplitter:
    def __init__(
        self,
        chunk_size: int = 700,
        chunk_overlap: int = 100,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "h1"),
                ("##", "h2"),
                ("###", "h3"),
                ("####", "h4"),
            ],
            strip_headers=False,
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n",
                "\n",
                ". ",
                "! ",
                "? ",
                "; ",
                ", ",
                " ",
                "",
            ],

            keep_separator=True,
            length_function=len,
        )
    def split(self, markdown: str):
        sections = self.header_splitter.split_text(markdown)
        chunks = self.text_splitter.split_documents(sections)
        return chunks