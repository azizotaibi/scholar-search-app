# app.py
from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import json
import os
from urllib.parse import quote

app = Flask(__name__)

# File to store author tags
TAGS_FILE = 'author_tags.json'

class ScholarSearcher:
    def __init__(self):
        self.base_url = "https://scholar.google.com/scholar"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def search_by_title(self, title, max_results=10):
        """Search Google Scholar by paper title"""
        query = f'intitle:"{title}"'
        params = {
            'q': query,
            'hl': 'en',
            'num': max_results
        }
        
        try:
            response = requests.get(self.base_url, params=params, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            papers = []
            
            for result in soup.find_all('div', class_='gs_r gs_or gs_scl'):
                paper = self.extract_paper_info(result)
                if paper:
                    papers.append(paper)
            
            return papers
        except Exception as e:
            print(f"Error searching: {e}")
            return []
    
    def extract_paper_info(self, result_div):
        """Extract paper information from search result"""
        try:
            # Title
            title_elem = result_div.find('h3', class_='gs_rt')
            title = title_elem.get_text() if title_elem else "Unknown Title"
            
            # Authors and publication info
            authors_elem = result_div.find('div', class_='gs_a')
            authors_text = authors_elem.get_text() if authors_elem else ""
            
            # Extract authors (usually before the first dash)
            authors = []
            if authors_text:
                author_part = authors_text.split(' - ')[0]
                authors = [author.strip() for author in author_part.split(',')]
            
            # Abstract/snippet
            snippet_elem = result_div.find('div', class_='gs_rs')
            snippet = snippet_elem.get_text() if snippet_elem else ""
            
            # Citation count
            cited_elem = result_div.find('a', string=lambda x: x and 'Cited by' in x)
            cited_by = 0
            if cited_elem:
                try:
                    cited_by = int(cited_elem.get_text().split('Cited by ')[1])
                except:
                    cited_by = 0
            
            return {
                'title': title,
                'authors': authors,
                'snippet': snippet,
                'cited_by': cited_by,
                'publication_info': authors_text
            }
        except Exception as e:
            print(f"Error extracting paper info: {e}")
            return None

class TagManager:
    def __init__(self, tags_file):
        self.tags_file = tags_file
        self.author_tags = self.load_tags()
    
    def load_tags(self):
        """Load author tags from file"""
        if os.path.exists(self.tags_file):
            try:
                with open(self.tags_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_tags(self):
        """Save author tags to file"""
        with open(self.tags_file, 'w') as f:
            json.dump(self.author_tags, f, indent=2)
    
    def add_tag(self, author, tag):
        """Add a tag to an author"""
        if author not in self.author_tags:
            self.author_tags[author] = []
        if tag not in self.author_tags[author]:
            self.author_tags[author].append(tag)
        self.save_tags()
    
    def remove_tag(self, author, tag):
        """Remove a tag from an author"""
        if author in self.author_tags and tag in self.author_tags[author]:
            self.author_tags[author].remove(tag)
            if not self.author_tags[author]:
                del self.author_tags[author]
            self.save_tags()
    
    def get_tags(self, author):
        """Get tags for an author"""
        return self.author_tags.get(author, [])
    
    def get_all_tags(self):
        """Get all unique tags"""
        all_tags = set()
        for tags in self.author_tags.values():
            all_tags.update(tags)
        return sorted(list(all_tags))
    
    def filter_papers_by_tags(self, papers, selected_tags):
        """Filter papers by author tags"""
        if not selected_tags:
            return papers
        
        filtered_papers = []
        for paper in papers:
            for author in paper['authors']:
                author_tags = self.get_tags(author)
                if any(tag in author_tags for tag in selected_tags):
                    # Add tag information to paper
                    paper['matching_authors'] = []
                    for auth in paper['authors']:
                        auth_tags = self.get_tags(auth)
                        matching_tags = [tag for tag in auth_tags if tag in selected_tags]
                        if matching_tags:
                            paper['matching_authors'].append({
                                'name': auth,
                                'tags': auth_tags,
                                'matching_tags': matching_tags
                            })
                    filtered_papers.append(paper)
                    break
        
        return filtered_papers

# Initialize components
searcher = ScholarSearcher()
tag_manager = TagManager(TAGS_FILE)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    title = data.get('title', '').strip()
    selected_tags = data.get('tags', [])
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    # Search Google Scholar
    papers = searcher.search_by_title(title)
    
    # Filter by tags if specified
    if selected_tags:
        papers = tag_manager.filter_papers_by_tags(papers, selected_tags)
    
    # Add tag information to all papers
    for paper in papers:
        for i, author in enumerate(paper['authors']):
            paper['authors'][i] = {
                'name': author,
                'tags': tag_manager.get_tags(author)
            }
    
    return jsonify({
        'papers': papers,
        'total': len(papers)
    })

@app.route('/tags', methods=['GET'])
def get_all_tags():
    return jsonify(tag_manager.get_all_tags())

@app.route('/add_tag', methods=['POST'])
def add_tag():
    data = request.json
    author = data.get('author', '').strip()
    tag = data.get('tag', '').strip()
    
    if not author or not tag:
        return jsonify({'error': 'Author and tag are required'}), 400
    
    tag_manager.add_tag(author, tag)
    return jsonify({'success': True})

@app.route('/remove_tag', methods=['POST'])
def remove_tag():
    data = request.json
    author = data.get('author', '').strip()
    tag = data.get('tag', '').strip()
    
    if not author or not tag:
        return jsonify({'error': 'Author and tag are required'}), 400
    
    tag_manager.remove_tag(author, tag)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)