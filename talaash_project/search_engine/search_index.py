import re
import os
import json
from collections import defaultdict
from django.conf import settings
from .models import Document

class BigramIndex:
    def __init__(self):
        self.index = defaultdict(set)  # bigram -> set of words mapping
        self.word_docs = defaultdict(set)  # word -> set of doc_ids mapping
        self.doc_stats = {}  # Document statistics
        
        # Load punctuations and stopwords
        self.punctuations = self.load_punctuations(os.path.join(settings.BASE_DIR, 'search_engine/static/punctuations.txt'))
        self.stopwords = self.load_stopwords(os.path.join(settings.BASE_DIR, 'search_engine/static/stopwords.txt'))
        
        # Check if index files exist
        self.index_file = os.path.join(settings.BASE_DIR, 'search_engine/static/output/index.json')
        self.bigrams_file = os.path.join(settings.BASE_DIR, 'search_engine/static/output/bigrams.json')
        
        # If index files exist, load them
        if os.path.exists(self.index_file) and os.path.exists(self.bigrams_file):
            self.load_index_from_files()
        else:
            # Build the index from scratch - this will be empty until parse_reuters is called
            pass

    def load_punctuations(self, filename):
        try:
            with open(filename, "r") as f:
                return set(f.read().strip())
        except FileNotFoundError:
            # Default punctuations if file not found
            return set('.,;:!?()[]{}"\'`~@#$%^&*-_=+<>/\\|')

    def load_stopwords(self, filename):
        try:
            with open(filename, "r") as f:
                return set(f.read().strip().splitlines())
        except FileNotFoundError:
            # Default stopwords if file not found
            return set(['a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what', 'which', 'this', 'that', 'these', 'those', 'then', 'just', 'so', 'than', 'such', 'both', 'through', 'about', 'for', 'is', 'of', 'while', 'during', 'to'])

    def load_index_from_files(self):
        """Load the index from previously saved JSON files"""
        try:
            with open(self.index_file, 'r') as f:
                word_docs_dict = json.load(f)
                # Convert lists back to sets
                self.word_docs = {k: set(v) for k, v in word_docs_dict.items()}
            
            with open(self.bigrams_file, 'r') as f:
                bigrams_dict = json.load(f)
                # Convert lists back to sets
                self.index = {k: set(v) for k, v in bigrams_dict.items()}
                
            print(f"Loaded {len(self.word_docs)} words and {len(self.index)} bigrams from files")
        except Exception as e:
            print(f"Error loading index files: {e}")
            # Initialize empty indexes
            self.index = defaultdict(set)
            self.word_docs = defaultdict(set)

    def save_index_to_files(self):
        """Save the current index to JSON files"""
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
        
        try:
            with open(self.index_file, 'w') as f:
                # Convert sets to lists for JSON serialization
                json.dump({k: list(v) for k, v in self.word_docs.items()}, f, indent=4)
                
            with open(self.bigrams_file, 'w') as f:
                # Convert sets to lists for JSON serialization
                json.dump({k: list(v) for k, v in self.index.items()}, f, indent=4)
                
            print(f"Saved {len(self.word_docs)} words and {len(self.index)} bigrams to files")
        except Exception as e:
            print(f"Error saving index files: {e}")

    def clean_and_tokenize(self, text):
        # Remove punctuations
        text = ''.join(char if char not in self.punctuations else ' ' for char in text)
        # Convert to lowercase and split
        tokens = text.lower().split()
        # Remove stopwords
        tokens = [token for token in tokens if token not in self.stopwords]
        return tokens

    def add_document(self, doc_id, text):
        # Clean and tokenize text
        words = self.clean_and_tokenize(text)

        # Update document statistics
        self.doc_stats[doc_id] = {
            'total_words': len(words),
            'unique_words': len(set(words))
        }

        # Process each word
        for word in words:
            self.word_docs[word].add(doc_id)

            # Create bigrams for the word
            word_with_boundaries = f"${word}$"
            for i in range(len(word_with_boundaries) - 1):
                bigram = word_with_boundaries[i:i + 2]
                self.index[bigram].add(word)

    def parse_file(self, file_path):
        with open(file_path, encoding='latin1') as f:
            content = f.read()

        # Split using REUTERS tag
        documents = re.findall(r'<REUTERS.*?</REUTERS>', content, flags=re.DOTALL)
        for document in documents:
            doc_id_match = re.search(r'NEWID="(\d+)"', document)
            doc_id = int(doc_id_match.group(1)) if doc_id_match else None

            if doc_id:
                title_match = re.search(r'<TITLE>(.*?)</TITLE>', document, flags=re.DOTALL)
                body_match = re.search(r'<BODY>(.*?)&#3;</BODY>', document, flags=re.DOTALL)

                title = title_match.group(1) if title_match else ''
                body = body_match.group(1) if body_match else ''

                # Add document to index
                self.add_document(doc_id, title + " " + body)
                
                # Also add to Django database
                Document.objects.update_or_create(
                    id=doc_id,
                    defaults={
                        'title': title,
                        'description': body
                    }
                )

    def parse_reuters(self, reuters_dir):
        """Parse all Reuters files and build the index"""
        # Count for reporting
        file_count = 0
        doc_count = 0
        
        for filename in os.listdir(reuters_dir):
            if filename.endswith('.sgm'):
                print(f'Processing {filename}...')
                file_path = os.path.join(reuters_dir, filename)
                self.parse_file(file_path)
                file_count += 1
        
        # Save index to files
        self.save_index_to_files()
        
        # Count documents
        doc_count = Document.objects.count()
        
        return file_count, doc_count

    def process_query(self, query_type, query_text):
        """Process a query based on its type"""
        # Clean query text (remove stopwords and punctuations)
        cleaned_query = ' '.join(self.clean_and_tokenize(query_text))
        
        if query_type == 'type1':
            # Add 'and' between words
            if ' ' in cleaned_query:
                words = cleaned_query.split()
                processed_query = ' and '.join(words)
            else:
                processed_query = cleaned_query
            return self.type1_query(processed_query)
        
        elif query_type == 'type2':
            # Add 'or' between words
            if ' ' in cleaned_query:
                words = cleaned_query.split()
                processed_query = ' or '.join(words)
            else:
                processed_query = cleaned_query
            return self.type2_query(processed_query)
        
        elif query_type == 'type3':
            # Wildcard search
            return self.type3_query(query_text)
        
        return []

    def intersect(self, lst1, lst2):
        return list(set(lst1) & set(lst2))

    def union(self, lst1, lst2):
        return list(set(lst1) | set(lst2))

    def type1_query(self, query):
        keywords = query.lower().split(" and ")
        result = set()
        first = True
        
        for keyword in keywords:
            if keyword in self.word_docs:
                if first:
                    result = self.word_docs[keyword]
                    first = False
                else:
                    result = self.intersect(result, self.word_docs[keyword])
            else:
                return []
                
        return sorted(list(result))

    def type2_query(self, query):
        keywords = query.lower().split(" or ")
        result = set()
        
        for keyword in keywords:
            if keyword in self.word_docs:
                result.update(self.word_docs[keyword])
                
        return sorted(list(result))

    # def wildcard_search(self, pattern):
    #     if '*' not in pattern:
    #         return []

    #     prefix, suffix = pattern.lower().split('*', 1)

    #     # Get prefix candidates
    #     candidates = None
    #     if prefix:
    #         prefix = f"${prefix}"
    #         for i in range(len(prefix) - 1):
    #             bigram = prefix[i:i + 2]
    #             bigram_words = self.index.get(bigram, set())
    #             if candidates is None:
    #                 candidates = bigram_words
    #             else:
    #                 candidates &= bigram_words

    #     # Get suffix candidates
    #     if suffix:
    #         suffix = f"{suffix}$"
    #         suffix_candidates = None
    #         for i in range(len(suffix) - 1):
    #             bigram = suffix[i:i + 2]
    #             bigram_words = self.index.get(bigram, set())
    #             if suffix_candidates is None:
    #                 suffix_candidates = bigram_words
    #             else:
    #                 suffix_candidates &= bigram_words

    #         if candidates is None:
    #             candidates = suffix_candidates
    #         elif suffix_candidates is not None:
    #             candidates &= suffix_candidates

    #     if not candidates:
    #         return []

    #     # Filter using regex
    #     pattern = pattern.replace('*', '.*')
    #     matches = [word for word in candidates if re.match(f"^{pattern}$", word)]
        
    #     # Get document IDs for matching words
    #     doc_ids = set()
    #     for word in matches:
    #         doc_ids.update(self.word_docs[word])
            
    #     return sorted(list(doc_ids))


    def wildcard_search(self, pattern):
        if '*' not in pattern:
            return []

        prefix, suffix = pattern.lower().split('*', 1)

        # Debug: Print prefix and suffix
        print(f"Prefix: {prefix}, Suffix: {suffix}")

        # Get prefix candidates
        candidates = None
        if prefix:
            prefix = f"${prefix}"
            for i in range(len(prefix) - 1):
                bigram = prefix[i:i + 2]
                bigram_words = self.index.get(bigram, set())
                print(f"Bigram: {bigram}, Words: {bigram_words}")  # Debug statement
                if candidates is None:
                    candidates = bigram_words
                else:
                    candidates &= bigram_words

        # Get suffix candidates
        if suffix:
            suffix = f"{suffix}$"
            suffix_candidates = None
            for i in range(len(suffix) - 1):
                bigram = suffix[i:i + 2]
                bigram_words = self.index.get(bigram, set())
                print(f"Bigram: {bigram}, Words: {bigram_words}")  # Debug statement
                if suffix_candidates is None:
                    suffix_candidates = bigram_words
                else:
                    suffix_candidates &= bigram_words

            if candidates is None:
                candidates = suffix_candidates
            elif suffix_candidates is not None:
                candidates &= suffix_candidates

        # Debug: Print candidates before regex filtering
        print(f"Candidates before regex: {candidates}")

        if not candidates:
            return []

        # Filter using regex
        pattern = pattern.replace('*', '.*')
        matches = [word for word in candidates if re.match(f"^{pattern}$", word)]

        # Debug: Print matches after regex filtering
        print(f"Matches after regex: {matches}")

        # Get document IDs for matching words
        doc_ids = set()
        for word in matches:
            doc_ids.update(self.word_docs[word])

        return sorted(list(doc_ids))
    
    def type3_query(self, pattern):
        return self.wildcard_search(pattern)