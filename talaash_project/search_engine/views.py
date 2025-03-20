from django.shortcuts import render, get_object_or_404, redirect
from .models import Document
from .search_index import BigramIndex
from django.http import Http404

# Global instance of BigramIndex
index = None

def initialize_index():
    global index
    if index is None:
        index = BigramIndex()
    return index

def home(request):
    """Home page with search functionality"""
    return render(request, 'search_engine/home.html')

def search_results(request):
    """Process search query and display results"""
    if request.method == 'GET':
        # Get query from GET parameters
        full_query = request.GET.get('q', '')
        
        if not full_query:
            return redirect('home')
        
        # Split query type and actual query
        parts = full_query.split(' ', 1)
        if len(parts) < 2:
            # Invalid query format
            return render(request, 'search_engine/results.html', {
                'query': full_query,
                'error': 'Invalid query format. Please specify type (type1, type2, type3) followed by your search terms.',
                'results': []
            })
        
        query_type, query_text = parts
        
        # Validate query type
        if query_type not in ['type1', 'type2', 'type3']:
            return render(request, 'search_engine/results.html', {
                'query': full_query,
                'error': 'Invalid query type. Use type1, type2, or type3.',
                'results': []
            })
        
        # Initialize the index if not already done
        search_index = initialize_index()
        
        # Process the query
        doc_ids = search_index.process_query(query_type, query_text)
        
        # Get documents for the returned IDs
        results = []
        for doc_id in doc_ids:
            try:
                doc = Document.objects.get(id=doc_id)
                results.append(doc)
            except Document.DoesNotExist:
                # Skip documents that no longer exist in the database
                continue
        
        return render(request, 'search_engine/results.html', {
            'query': full_query,
            'results': results
        })
    
    return redirect('home')

def document_detail(request, doc_id):
    """Display details of a specific document"""
    document = get_object_or_404(Document, id=doc_id)
    return render(request, 'search_engine/document_detail.html', {'document': document})

def refresh_index(request):
    """Refresh the search index (admin functionality)"""
    global index
    index = BigramIndex()
    return redirect('home')