"""Conservative, line-based segmentation; never treat a citation as an annex heading."""
import re
from .util import stable_id

ARTICLE = re.compile(r'^Điều\s+\d+[a-zđ]?[.:\s]', re.I)
ATTACHMENT = re.compile(r'^(PHỤ LỤC(?:\s+[IVXLCDM\dA-Z]+)?|MẪU(?:\s+SỐ)?\s+\d+[A-Z]?)(?:\s|[.:]|$)', re.I)


def segment_document(doc, text, keep_preamble=True):
    # Repair old extraction's glued uppercase chapter titles, not ordinary citations.
    def heading(match):
        return match[1]+'\n'+match[2] if match[1].isupper() else match[0]
    text=re.sub(r'^([^\n]+?)\s+(Điều\s+\d+[a-zđ]?\.\s+[^\n]+)$',heading,text,flags=re.M)
    lines=text.splitlines(); segments=[]; start=0; kind='PREAMBLE'; seen_article=False
    def emit(end):
        content='\n'.join(lines[start:end]).strip()
        if content and (kind!='PREAMBLE' or keep_preamble):
            segments.append({'segment_id':stable_id(doc['document_id'],kind,str(start+1),prefix='seg'),
                'document_id':doc['document_id'],'segment_type':kind,'text':content,
                'line_start':start+1,'line_end':end,'heading':lines[start].strip() if start<len(lines) else ''})
    for i,line in enumerate(lines):
        s=line.strip().lstrip('#').strip(); new=None
        if not seen_article and ARTICLE.match(s):
            new='MAIN_BODY'; seen_article=True
        elif seen_article and ATTACHMENT.match(s) and len(s)<180:
            # A complete standalone header, not 'Phụ lục này...' inside running prose.
            token=ATTACHMENT.match(s).group(1)
            if s.isupper() or re.fullmatch(r'(?:Phụ lục|Mẫu(?: số)?)\s*[IVXLCDM\dA-Z]*[.:]?',s):
                new='FORM' if token.upper().startswith('MẪU') else 'ANNEX'
        elif seen_article and s.upper() in {'ĐỀ CƯƠNG BÁO CÁO','DANH MỤC'}:
            new='ANNEX'
        elif seen_article and re.match(r'^(?:Nơi nhận\s*:|KT\.\s|TM\.\s)',s):
            new='SIGNATURE'
        # Attached regulations can have their own genuine Article hierarchy.
        elif seen_article and s.upper() in {'QUY ĐỊNH','QUY CHẾ'} and kind in {'SIGNATURE','ANNEX'}:
            new='ATTACHED_REGULATION'
        if new and (new!=kind or new in {'FORM','ANNEX','ATTACHED_REGULATION'}):
            emit(i); start=i; kind=new
    emit(len(lines))
    return segments
