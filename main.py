import re
import os
import json
from io import BytesIO
from PIL import Image


class GeminiOCR:
    def __init__(self, api_key):
        """
        Inicializa o GeminiOCR com a chave API do Gemini
        """
        self.api_key = api_key
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")
        # Para acompanhar o progresso do PDF
        self.current_page = 0
        self.total_pages = 0
        self.processed_pages = []

    def process_document(self, file_path, start_page=0):
        """
        Interface principal para processamento de documento (PDF ou imagem)
        """
        try:
            file_ext = file_path.lower().split(".")[-1]
            output_dir = os.path.dirname(file_path)
            file_base = os.path.basename(file_path).rsplit(".", 1)[0]

            if file_ext == "pdf":
                return self._process_pdf(file_path, output_dir, file_base, start_page)
            else:  # Assume que é uma imagem
                return self._process_technical(file_path, Image.open(file_path))

        except Exception as e:
            print(f"Erro no processamento: {e}")
            return None

    def _process_pdf(self, pdf_path, output_dir, file_base, start_page=0):
        """
        Processa um arquivo PDF, extraindo e processando cada página
        """
        try:
            import fitz  # PyMuPDF

            # Abre o PDF
            pdf_document = fitz.open(pdf_path)
            self.total_pages = len(pdf_document)
            self.current_page = max(0, min(start_page, self.total_pages - 1))

            # Arquivo de saída único
            output_html = os.path.join(output_dir, f"{file_base}_processado.html")

            # Arquivo de controle de progresso
            progress_file = os.path.join(output_dir, f"{file_base}_progresso.json")

            # Carrega progresso anterior se existir
            if os.path.exists(progress_file):
                with open(progress_file, "r", encoding="utf-8") as f:
                    progress_data = json.load(f)
                    self.processed_pages = progress_data.get("processed_pages", [])

                    if (
                        self.current_page == 0
                        and progress_data.get("last_page") is not None
                    ):
                        # Se não especificou uma página de início, continua de onde parou
                        self.current_page = progress_data.get("last_page") + 1
                        print(
                            f"Continuando de onde parou: página {self.current_page + 1}"
                        )
            else:
                self.processed_pages = []

            print(
                f"Iniciando processamento do PDF com {self.total_pages} páginas a partir da página {self.current_page + 1}"
            )

            # Inicializa ou carrega conteúdo HTML existente
            existing_content = {}
            if os.path.exists(output_html):
                existing_content = self._extract_existing_content(output_html)

            try:
                all_content = ""
                last_processed = None

                for page_num in range(self.current_page, self.total_pages):
                    self.current_page = page_num

                    # Verifica se a página já foi processada
                    if (
                        page_num in self.processed_pages
                        and page_num in existing_content
                    ):
                        print(f"Página {page_num + 1} já processada, pulando...")
                        all_content += existing_content[page_num]
                        continue

                    print(f"Processando página {page_num + 1} de {self.total_pages}...")

                    # Extrai a página como imagem
                    page = pdf_document[page_num]
                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(2, 2)
                    )  # Aumenta a resolução para melhor OCR

                    # Converte para imagem PIL
                    img = Image.open(BytesIO(pix.tobytes("png")))

                    # Processa a imagem da página
                    page_content = self._process_page_content(
                        img, page_num + 1, self.total_pages
                    )
                    all_content += page_content

                    # Registra progresso
                    if page_num not in self.processed_pages:
                        self.processed_pages.append(page_num)

                    last_processed = page_num

                    # Atualiza arquivo de progresso após cada página
                    self._update_progress_file(progress_file, last_processed)

                    # Salva o HTML atual após cada página (para não perder o trabalho)
                    self._save_html_file(output_html, all_content)

                    print(
                        f"Página {page_num + 1} processada com sucesso! Progresso salvo."
                    )

                # Finaliza e salva o arquivo HTML completo
                print(
                    f"Processamento completo! {len(self.processed_pages)}/{self.total_pages} páginas processadas."
                )
                print(f"Arquivo HTML salvo em: {output_html}")
                return output_html

            except Exception as e:
                print(f"\n=== ERRO DURANTE O PROCESSAMENTO ===")
                print(f"Erro: {e}")
                print(f"Processamento interrompido na página {self.current_page + 1}.")
                print(
                    f"Páginas processadas: {len(self.processed_pages)}/{self.total_pages}"
                )
                print(
                    f"Última página processada: {last_processed + 1 if last_processed is not None else 'Nenhuma'}"
                )
                print(f"Para continuar o processamento use:")
                print(
                    f"ocr.process_document('{pdf_path}', start_page={self.current_page + 1})"
                )
                print(f"===================================\n")

                # Mesmo com erro, salva o que foi processado até agora
                if all_content:
                    self._save_html_file(output_html, all_content)
                    return output_html
                return None

        except ImportError:
            print("PyMuPDF (fitz) não está instalado. Instale com: pip install pymupdf")
            return None
        except Exception as e:
            print(f"Erro ao processar PDF: {e}")
            return None

    def _extract_existing_content(self, html_path):
        """Extrai o conteúdo existente de páginas já processadas do arquivo HTML"""
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            # Padrão para extrair seções de página
            pattern = r'<div class="page-content" data-page="(\d+)">(.*?)<div class="page-footer">'
            matches = re.findall(pattern, html_content, re.DOTALL)

            content_dict = {}
            for match in matches:
                page_num = int(match[0]) - 1  # Converter para base 0
                content = match[1] + '<div class="page-footer">'
                content_dict[page_num] = content

            return content_dict
        except Exception as e:
            print(f"Aviso: Não foi possível extrair conteúdo existente: {e}")
            return {}

    def _update_progress_file(self, progress_file, last_processed):
        """Atualiza o arquivo de controle de progresso"""
        progress_data = {
            "total_pages": self.total_pages,
            "processed_pages": sorted(self.processed_pages),
            "last_page": last_processed,
            "progress_percentage": round(
                len(self.processed_pages) * 100 / self.total_pages, 2
            ),
        }

        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(progress_data, f, indent=2)

    def _save_html_file(self, output_path, content):
        """Salva o conteúdo no arquivo HTML final"""
        html = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Documento Processado</title>
            
            <!-- MathJax Config -->
            <script>
            MathJax = {{
                tex: {{
                    inlineMath: [['$', '$']],
                    displayMath: [['$$', '$$']],
                    processEscapes: true
                }},
                svg: {{
                    fontCache: 'global'
                }}
            }};
            </script>
            <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
            <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
            
            <style>
                :root {{
                    --text-color: #333;
                    --bg-color: #fff;
                    --content-bg: #ffffff;
                    --equation-bg: #f8f9fa;
                    --line-height: 1.6;
                    --font-size: 16px;
                }}
                
                body {{
                    font-family: Arial, sans-serif;
                    line-height: var(--line-height);
                    font-size: var(--font-size);
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: var(--bg-color);
                    color: var(--text-color);
                }}
                
                .content {{
                    background-color: var(--content-bg);
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    margin-bottom: 80px; /* Espaço para o menu de acessibilidade */
                }}
                
                .equation {{
                    margin: 1em 0;
                    padding: 1em;
                    background: var(--equation-bg);
                    border-radius: 8px;
                    overflow-x: auto;
                }}
                
                .page-header {{
                    background-color: #e3f2fd;
                    padding: 10px;
                    margin: 30px 0 10px 0;
                    border-radius: 5px;
                    text-align: center;
                    font-weight: bold;
                    font-size: 18px;
                    border-bottom: 2px solid #2196F3;
                }}
                
                .page-footer {{
                    border-bottom: 1px dashed #ccc;
                    margin: 20px 0;
                    padding-bottom: 10px;
                }}
                
                .index {{
                    background-color: #f5f5f5;
                    padding: 15px;
                    border-radius: 8px;
                    margin-bottom: 30px;
                }}
                
                .index h2 {{
                    margin-top: 0;
                    color: #2196F3;
                }}
                
                .index-links {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                }}
                
                .index-link {{
                    display: inline-block;
                    padding: 5px 10px;
                    background: #e3f2fd;
                    border-radius: 5px;
                    text-decoration: none;
                    color: #0056b3;
                }}
                
                .index-link:hover {{
                    background: #bbdefb;
                }}
                
                .accessibility-controls {{
                    position: fixed;
                    bottom: 20px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: var(--content-bg);
                    padding: 10px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: center;
                    gap: 5px;
                    z-index: 1000;
                    max-width: 320px; /* Tamanho fixo */
                    width: auto;
                }}
                
                button {{
                    padding: 6px 12px;
                    border: none;
                    border-radius: 4px;
                    background: #007bff;
                    color: white;
                    cursor: pointer;
                    transition: background 0.3s;
                    font-size: 14px;
                }}
                
                button:hover {{
                    background: #0056b3;
                }}
                
                /* Temas */
                body.dark-mode {{
                    --text-color: #e0e0e0;
                    --bg-color: #1a1a1a;
                    --content-bg: #2d2d2d;
                    --equation-bg: #363636;
                }}
                
                body.high-contrast {{
                    --text-color: #fff;
                    --bg-color: #000;
                    --content-bg: #000;
                    --equation-bg: #333;
                }}
                
                /* Para acomodar o feedback de usuários com deficiência visual */
                @media (min-width: 769px) {{
                    .accessibility-controls {{
                        /* Tamanho fixo, não aumenta com zoom */
                        transform: translateX(-50%) scale(1);
                        transform-origin: center;
                    }}
                }}
                
                @media (max-width: 768px) {{
                    .accessibility-controls {{
                        max-width: 260px;
                        /* Tamanho fixo para mobile */
                        transform: translateX(-50%) scale(1);
                        transform-origin: center;
                    }}
                    
                    button {{
                        font-size: 12px;
                        padding: 4px 8px;
                    }}
                }}
                
                #progress-bar {{
                    position: fixed;
                    top: 0;
                    left: 0;
                    height: 5px;
                    background-color: #2196F3;
                    z-index: 1001;
                }}
                
                .top-link {{
                    display: inline-block;
                    position: fixed;
                    bottom: 70px;
                    right: 20px;
                    background: #2196F3;
                    color: white;
                    width: 40px;
                    height: 40px;
                    border-radius: 50%;
                    text-align: center;
                    line-height: 40px;
                    font-size: 20px;
                    text-decoration: none;
                    opacity: 0.7;
                    transition: opacity 0.3s;
                }}
                
                .top-link:hover {{
                    opacity: 1;
                }}
            </style>
        </head>
        <body>
            <header>
                <h1>Documento Processado</h1>
                <div id="progress-bar" style="width: {round(len(self.processed_pages) * 100 / self.total_pages, 2)}%;"></div>
                <p><strong>Progresso:</strong> {len(self.processed_pages)}/{self.total_pages} páginas processadas ({round(len(self.processed_pages) * 100 / self.total_pages, 2)}%)</p>
            </header>
            
            <div class="index">
                <h2>Índice de Páginas</h2>
                <div class="index-links">
                    {self._generate_index_links()}
                </div>
            </div>
            
            <main role="main" class="content">
                {content}
            </main>
            
            <a href="#top" class="top-link" aria-label="Voltar ao topo">↑</a>
            
            <div class="accessibility-controls" aria-label="Controles de acessibilidade">
                <button onclick="toggleDarkMode()" aria-label="Alternar modo escuro">🌓</button>
                <button onclick="toggleHighContrast()" aria-label="Alternar alto contraste">👁️</button>
                <button onclick="increaseFontSize()" aria-label="Aumentar tamanho da fonte">A+</button>
                <button onclick="decreaseFontSize()" aria-label="Diminuir tamanho da fonte">A-</button>
                <button onclick="increaseLineHeight()" aria-label="Aumentar espaçamento entre linhas">↕️+</button>
                <button onclick="decreaseLineHeight()" aria-label="Diminuir espaçamento entre linhas">↕️-</button>
            </div>
            
            <script>
                // Adiciona links de página ao carregar
                document.addEventListener('DOMContentLoaded', function() {{
                    // Gera links para navegação rápida
                    const pageHeaders = document.querySelectorAll('.page-header');
                    pageHeaders.forEach(header => {{
                        const pageNum = header.getAttribute('id').replace('page-', '');
                        const pageId = `page-${{pageNum}}`;
                        
                        // Adiciona links no índice se não existirem
                        if (!document.querySelector(`.index-link[href="#${{pageId}}"]`)) {{
                            const indexLinks = document.querySelector('.index-links');
                            if (indexLinks) {{
                                const link = document.createElement('a');
                                link.href = `#${{pageId}}`;
                                link.className = 'index-link';
                                link.textContent = `Página ${{pageNum}}`;
                                indexLinks.appendChild(link);
                            }}
                        }}
                    }});
                    
                    // Scroll para a página se vier com hash
                    if (window.location.hash) {{
                        const targetElement = document.querySelector(window.location.hash);
                        if (targetElement) {{
                            targetElement.scrollIntoView();
                        }}
                    }}
                }});
                
                function toggleDarkMode() {{
                    document.body.classList.toggle('dark-mode');
                    document.body.classList.remove('high-contrast');
                    refreshMathJax();
                }}
                
                function toggleHighContrast() {{
                    document.body.classList.toggle('high-contrast');
                    document.body.classList.remove('dark-mode');
                    refreshMathJax();
                }}
                
                let currentFontSize = 16;
                function increaseFontSize() {{
                    currentFontSize = Math.min(currentFontSize * 1.1, 32);
                    document.documentElement.style.setProperty('--font-size', currentFontSize + 'px');
                    refreshMathJax();
                }}
                
                function decreaseFontSize() {{
                    currentFontSize = Math.max(currentFontSize * 0.9, 12);
                    document.documentElement.style.setProperty('--font-size', currentFontSize + 'px');
                    refreshMathJax();
                }}
                
                let currentLineHeight = 1.6;
                function increaseLineHeight() {{
                    currentLineHeight = Math.min(currentLineHeight * 1.1, 2.5);
                    document.documentElement.style.setProperty('--line-height', currentLineHeight);
                }}
                
                function decreaseLineHeight() {{
                    currentLineHeight = Math.max(currentLineHeight * 0.9, 1.2);
                    document.documentElement.style.setProperty('--line-height', currentLineHeight);
                }}
                
                function refreshMathJax() {{
                    if (typeof MathJax !== 'undefined') {{
                        MathJax.typesetClear();
                        MathJax.typesetPromise();
                    }}
                }}
            </script>
        </body>
        </html>
        """

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    def _generate_index_links(self):
        """Gera os links para o índice com base nas páginas processadas"""
        links = ""
        for page in sorted(self.processed_pages):
            page_num = page + 1  # Página 0 é a página 1 para o usuário
            links += (
                f'<a href="#page-{page_num}" class="index-link">Página {page_num}</a>\n'
            )
        return links

    def _process_page_content(self, image, page_num, total_pages):
        """Processa o conteúdo de uma página e retorna HTML formatado"""
        prompt = r"""
        Analise esta imagem e extraia:
        1. Texto completo preservando a formatação
        2. Equações matemáticas em LaTeX (use $$ para display mode, $ para inline)
        3. Mantenha a precisão técnica do conteúdo
        4. Preserve símbolos especiais e notações matemáticas
        
        IMPORTANTE para notação matemática:
        1. Use \arcsin (não extarcsen ou arcsen)
        2. Use \arccos (não extarccos ou arccos)
        3. Use \arctan (não extarctan ou arctan)
        4. Use \sin (não sen)
        5. Use \cos (não cos)
        6. Use \tan (não tan)
        7. Use \sqrt{} para raiz quadrada
        8. Use \frac{}{} para frações
        
        Para expressões matemáticas:
        - Use $ $ para equações inline
        - Use $$ $$ para equações em display mode
        - Preserve todos os parênteses e sinais
        - Mantenha a formatação precisa das funções trigonométricas
        
        Mantenha a estrutura do documento e a formatação original.
        """

        result = self.model.generate_content([prompt, image])
        cleaned_result = self._clean_text(result)

        # Formata o conteúdo da página com cabeçalho e rodapé identificáveis
        page_content = f"""
        <div class="page-header" id="page-{page_num}">Página {page_num} de {total_pages}</div>
        <div class="page-content" data-page="{page_num}">
            {cleaned_result}
        </div>
        <div class="page-footer"></div>
        """

        return page_content

    def _clean_text(self, response):
        """Limpa o texto removendo artefatos indesejados"""
        # Primeiro extraímos o texto do objeto GenerateContentResponse
        if hasattr(response, "text"):
            text = response.text
        else:
            raise ValueError("Resposta do Gemini não contém texto")

        replacements = {
            r"\u00e7": "ç",
            r"\u00f5": "õ",
            r"\u00e3": "ã",
            r"\n": "\n",
            r"\t": "    ",
            "\u2013": "-",
            "\u2014": "-",
            r"\u00ed": "í",
            r"\u00e1": "á",
            r"\u00e9": "é",
            r"\u00fa": "ú",
            r"\u00f3": "ó",
            "\\\\": "\\",
            "\u20134": "-",
            "\u22121": "-",
            "\u20132": "-",
            "\u20133": "-",
        }

        # Remove sequências de escape e códigos Unicode
        cleaned_text = text
        for old, new in replacements.items():
            cleaned_text = cleaned_text.replace(old, new)

        # Remove caracteres de controle remanescentes
        cleaned_text = re.sub(r"\\u[0-9a-fA-F]{4}", "", cleaned_text)

        # Remove espaços múltiplos
        cleaned_text = re.sub(r"\s+", " ", cleaned_text)

        # Garante quebras de linha apropriadas
        cleaned_text = re.sub(r"\\n", "\n", cleaned_text)

        return cleaned_text

    def _process_technical(self, image_path, image):
        """Processa no modo técnico para compatibilidade com o código original"""
        # Determina o caminho de saída baseado no caminho de entrada
        output_path = f"{image_path.rsplit('.', 1)[0]}_tecnico.html"

        # Processa a imagem
        content = self._process_page_content(image, 1, 1)
        self._save_html_file(output_path, content)

        return output_path


api_key = "suachave"
ocr = GeminiOCR(api_key)

# Para processar um PDF:
output = ocr.process_document("caminho_arquivo.pdf ou png")
# Para retomar o processamento a partir de uma página específica:
# output = ocr.process_document("caminho/para/documento.pdf", start_page=5)  # Começa da página 6
# Para processar uma imagem (como antes):
# output = ocr.process_document("caminho/para/imagem.png")
