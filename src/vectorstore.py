import chromadb
from tqdm import tqdm
from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from typing import List, Optional
from langchain_core.documents import Document
from langchain_chroma import Chroma


class VectorStore:
    def __init__(self, persist_directory: str, model_name: str = "BAAI/bge-m3"):
        """
        벡터스토어 초기화

        Args:
            persist_directory (str): 벡터스토어를 저장할 디렉토리 경로
            model_name (str): HuggingFace 임베딩 모델 이름
        """
        self.persist_directory = persist_directory
        self.embedding = HuggingFaceEmbeddings(model_name=model_name)

        # Chroma 클라이언트 설정
        self.client = chromadb.PersistentClient(path=persist_directory)

        # Langchain Chroma 벡터스토어 초기화
        self.vectorstore = Chroma(
            persist_directory=persist_directory,
            embedding_function=self.embedding,
            client=self.client,
        )

    @staticmethod
    def load_pdf(filepath: str, chunk_size: int = 1000, chunk_overlap: int = 30):
        """
        PDF 파일을 로드하고 청크로 분할

        Args:
            filepath (str): PDF 파일 경로
            chunk_size (int): 청크 크기
            chunk_overlap (int): 청크 간 중복 크기

        Returns:
            List[Document]: 분할된 문서 리스트
        """
        # PDF 로드
        loader = PyPDFLoader(filepath)
        pages = loader.load_and_split()

        # 텍스트 분할
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

        return text_splitter.split_documents(pages)

    def add_documents(
        self, documents: List[Document], collection_name: Optional[str] = None
    ):
        """
        문서를 벡터스토어에 추가

        Args:
            documents (List[Document]): 추가할 문서 리스트
            collection_name (str, optional): 컬렉션 이름
        """
        if collection_name:
            # 컬렉션이 이미 존재하는지 확인
            try:
                existing_collection = self.client.get_collection(collection_name)
                # 기존 컬렉션이 있으면 문서만 추가
                vectorstore = Chroma(
                    client=self.client,
                    collection_name=collection_name,
                    embedding_function=self.embedding,
                )
                vectorstore.add_documents(documents)
            except ValueError:
                # 컬렉션이 없으면 새로 생성
                self.vectorstore = Chroma.from_documents(
                    documents=documents,
                    embedding=self.embedding,
                    persist_directory=self.persist_directory,
                    collection_name=collection_name,
                    client=self.client,
                )
        else:
            self.vectorstore.add_documents(documents)

        # 변경사항 저장
        self.vectorstore.persist()

    def similarity_search(
        self, query: str, k: int = 4, collection_name: Optional[str] = None
    ):
        """
        유사도 검색 수행

        Args:
            query (str): 검색 쿼리
            k (int): 반환할 결과 개수
            collection_name (str, optional): 검색할 컬렉션 이름

        Returns:
            List[Document]: 검색된 문서 리스트
        """
        if collection_name:
            collection = self.client.get_collection(collection_name)
            vectorstore = Chroma(
                client=self.client,
                collection_name=collection_name,
                embedding_function=self.embedding,
            )
            return vectorstore.similarity_search(query, k=k)

        return self.vectorstore.similarity_search(query, k=k)

    def get_retriever(self, search_kwargs: Optional[dict] = None, **kwargs):
        """
        벡터스토어의 retriever를 반환

        Args:
            search_kwargs (dict, optional): 검색 관련 추가 인자
            **kwargs: 추가 인자

        Returns:
            VectorStoreRetriever: 검색을 위한 retriever 객체
        """
        if search_kwargs is None:
            search_kwargs = {"k": 4}

        return self.vectorstore.as_retriever(search_kwargs=search_kwargs, **kwargs)


def process_pdf_directory(
    vector_store: VectorStore, pdf_dir: str, collection_name: Optional[str] = None
):
    """
    지정된 디렉토리의 새로운 PDF 파일만 처리하여 벡터스토어에 추가

    Args:
        vector_store (VectorStore): 벡터스토어 인스턴스
        pdf_dir (str): PDF 파일들이 있는 디렉토리 경로
        collection_name (str, optional): 저장할 컬렉션 이름
    """
    # 이미 처리된 PDF 파일 목록을 저장할 파일 경로
    processed_files_path = Path(vector_store.persist_directory) / "processed_files.txt"

    # 이미 처리된 파일 목록 로드
    processed_files = set()
    if processed_files_path.exists():
        with open(processed_files_path, "r", encoding="utf-8") as f:
            processed_files = set(f.read().splitlines())

    # 새로운 PDF 파일 찾기
    pdf_files = list(Path(pdf_dir).glob("*.pdf"))
    new_pdf_files = [pdf for pdf in pdf_files if str(pdf) not in processed_files]

    if not new_pdf_files:
        print("처리할 새로운 PDF 파일이 없습니다.")
        return

    # 실제 처리할 파일 수를 먼저 출력
    print(f"처리할 새로운 PDF 파일: {len(new_pdf_files)}개")

    for pdf_path in tqdm(new_pdf_files, desc="PDF 처리 중"):
        try:
            documents = VectorStore.load_pdf(str(pdf_path))
            vector_store.add_documents(
                documents=documents, collection_name=collection_name
            )
            # 처리 완료된 파일 기록
            with open(processed_files_path, "a", encoding="utf-8") as f:
                f.write(f"{str(pdf_path)}\n")

            print(f"완료: {pdf_path}")

        except Exception as e:
            print(f"오류 발생 ({pdf_path}): {str(e)}")


# 파일이 직접 실행될 때만 실행되는 코드
if __name__ == "__main__":
    # 벡터스토어 초기화
    vector_store = VectorStore(persist_directory="./data/vectordb")

    # PDF 처리
    process_pdf_directory(
        vector_store=vector_store,
        pdf_dir="./data",
        collection_name="pdf_collection",  # 선택사항
    )
