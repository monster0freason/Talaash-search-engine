from django.core.management.base import BaseCommand
import os
from search_engine.search_index import BigramIndex

class Command(BaseCommand):
    help = 'Import Reuters dataset into the database and create index files'

    def add_arguments(self, parser):
        parser.add_argument('reuters_dir', type=str, help='Path to Reuters dataset directory')

    def handle(self, *args, **options):
        reuters_dir = options['reuters_dir']
        
        if not os.path.exists(reuters_dir):
            self.stdout.write(self.style.ERROR(f'Directory not found: {reuters_dir}'))
            return
        
        # Initialize BigramIndex
        index = BigramIndex()
        
        # Parse Reuters dataset
        self.stdout.write(f'Parsing Reuters dataset from {reuters_dir}...')
        file_count, doc_count = index.parse_reuters(reuters_dir)
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully processed {file_count} files and imported {doc_count} documents. '
            f'Index files created in static/output/'
        ))