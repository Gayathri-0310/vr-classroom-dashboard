import re
import pandas as pd

COLUMN_MAP = {'Timestamp': 'timestamp', 'Email Address': 'email', 'Programme': 'programme', 'Gender': 'gender', 'Have you used VR before?': 'experience', 'How do you mostly learn now?': 'methods', 'Classes give me enough practical exposure': 'practical', 'I can relate what I learn in class to real-world situations': 'relevance', 'I stay attentive throughout a projector-based lecture.': 'attention', 'Workshops and guest sessions are engaging and useful': 'workshops', 'What makes you lose interest in regular classes?': 'disengagement', 'Which subject do you find hardest to stay interested in, and why?': 'difficult_subject', 'How often do you feel "I\'ll never use this in real life"?': 'real_life', 'I understand what a VR classroom is.': 'understanding', 'Column 14': 'placeholder', 'Learning through VR would be more interesting than slides.': 'interest', 'VR would help me understand difficult concepts.': 'concepts', 'Which VR uses appeal to you?': 'activities', 'Which subjects would benefit most from VR?': 'benefit_subject', 'Any concerns about VR?': 'concerns', 'I would be comfortable using VR headsets in class': 'comfort', 'Preferred session length': 'duration', 'Preferred frequency': 'frequency', 'VR would improve my attention and retention.': 'retention', 'VR would improve my placement and practical skills.': 'placement', 'Would you support VR classrooms in our college?': 'support', 'Would you pay a small fee for VR sessions?': 'pay', 'Any suggestions to make classes more practical and engaging?': 'suggestions'}
RATINGS = ['practical','relevance','attention','workshops','understanding','interest','concepts','comfort','retention','placement']
MULTI = ['methods','disengagement','activities','concerns']
TEXT = ['difficult_subject','benefit_subject','suggestions']
AGREE = {'Strongly disagree':1,'Disagree':2,'Neutral':3,'Agree':4,'Strongly agree':5}
LABELS = {'practical':'Practical exposure','relevance':'Real-world connection','attention':'Projector lecture attention','workshops':'Workshop engagement','understanding':'Understanding VR classrooms','interest':'Expected interest vs slides','concepts':'Expected concept understanding','comfort':'Headset comfort','retention':'Expected attention & retention','placement':'Expected placement & practical skills'}
THEMES = {
'Statistics / mathematics':r'statistic|math|calcul|algebr|quant|numbers|formula',
'Accounting / finance':r'account|financ|frpa|report|bank|tax',
'Management / business':r'management|mcob|organi[sz]|market|business|econom',
'Physics / engineering':r'physics|electri|engineering|eee|mech|electronic',
'Computing / programming':r'java|program|algorithm|daa|network|gen ai|web|computer',
'Practical / real-world learning':r'practic|real.life|real.time|hands.on|industry|industrial|simulation|role.?play|case stud',
'Interactive / visual learning':r'video|visual|animat|game|quiz|group|activit|interactive',
'Theory-heavy teaching':r'theor|boring|lecture|slides',
'VR adoption / access':r'\bvr\b|virtual|headset|connectiv',
}
EMPTY = {'','nil','na','n/a','none','nothing','no','no suggestion','no suggestions','no idea',"i don’t know","i don't know"}

def redact(v):
    if pd.isna(v): return pd.NA
    s=str(v).strip()
    s=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[redacted email]', s)
    s=re.sub(r'https?://\S+', '[redacted URL]', s)
    s=re.sub(r'(?<!\d)(?:\+?\d[\s-]?){10,}(?!\d)', '[redacted number]', s)
    if re.search(r'teacher is bad',s,re.I): s=re.sub('teacher is bad','[personal criticism withheld]',s,flags=re.I)
    if re.search(r'these university type lectures',s,re.I): s='Requests more engaging classroom teaching and clear explanations. [paraphrased]'
    return s if s else pd.NA

def substantive(v):
    if pd.isna(v): return False
    s=str(v).strip().lower().strip(' .…!')
    return s not in EMPTY and bool(re.search(r'[a-zA-Z]',s))

def prepare(raw):
    d=raw.copy(); d.columns=[str(c).strip() for c in d.columns]
    d=d.rename(columns=COLUMN_MAP)
    log=[]
    for c in d.select_dtypes(include=['object','string']).columns:
        d[c]=d[c].map(lambda x:x.strip() if isinstance(x,str) else x).replace('',pd.NA)
    known=set(COLUMN_MAP.values())|{'response_id','programme_original','duplicate_review'}
    unknown=[c for c in d if c not in known]
    if unknown: log.append('Unrecognized columns excluded: '+', '.join(unknown))
    d=d[[c for c in d if c in known]]
    if 'response_id' not in d: d.insert(0,'response_id',[f'R{i+1:03d}' for i in range(len(d))])
    missing=[c for c in COLUMN_MAP.values() if c not in d and c not in ['email','placeholder']]
    for c in missing: d[c]=pd.NA
    if missing: log.append('Missing columns shown as unavailable: '+', '.join(missing))
    if 'programme_original' not in d: d['programme_original']=d['programme']
    d['programme']=d['programme'].replace({'Mca':'MCA','mca':'MCA'})
    log.append('Trimmed headers and text; Mca/mca → MCA. I MBA and MBA retained separately; unusual programmes retained.')
    for c in RATINGS:
        rawcol=d[c].replace(AGREE)
        nums=pd.to_numeric(rawcol,errors='coerce')
        invalid=d[c].notna() & (~nums.between(1,5) | nums.mod(1).ne(0))
        if invalid.any(): log.append(f'{c}: {int(invalid.sum())} invalid ratings treated as missing.')
        d[c]=nums.where(nums.between(1,5)&nums.mod(1).eq(0))
    d['timestamp']=pd.to_datetime(d['timestamp'],errors='coerce')
    check=[c for c in COLUMN_MAP.values() if c in d and c not in ['email','timestamp','placeholder']]
    dup=d[check].astype('string').fillna('<missing>').duplicated(keep=False)
    if 'email' in d:
        e=d['email'].astype('string').str.lower()
        dup=dup | (e.notna() & e.duplicated(keep=False))
    if 'duplicate_review' in d: dup=dup | d['duplicate_review'].astype(str).str.lower().eq('true')
    d['duplicate_review']=dup
    log.append(f'{int(dup.sum())} responses flagged for duplicate review; none deleted. Matching repeated email or exact non-identifying answers is a flag, not proof.')
    for c in TEXT: d[c]=d[c].map(redact)
    log.append('Email and unexplained placeholder excluded. Free text receives email/URL/long-number redaction; known personal criticism withheld or paraphrased. Manual disclosure review remains advisable.')
    if 'placeholder' in d:
        log.append('Excluded placeholder values: '+str(d['placeholder'].value_counts(dropna=False).to_dict()))
    return d.drop(columns=['email','placeholder'],errors='ignore'), log

def load_book(source):
    book=pd.ExcelFile(source)
    scores=[]
    for sheet in book.sheet_names:
        header=pd.read_excel(book,sheet_name=sheet,nrows=0)
        score=sum(str(c).strip() in COLUMN_MAP or str(c).strip() in COLUMN_MAP.values() for c in header.columns)
        scores.append((score,sheet))
    score,sheet=max(scores,key=lambda p:p[0])
    if score<5: raise ValueError('No recognizable survey table found. Upload the original workbook or the supplied cleaned workbook.')
    d,log=prepare(pd.read_excel(book,sheet_name=sheet))
    log.insert(0,'Inspected sheets: '+', '.join(book.sheet_names)+'. Selected: '+sheet)
    return d,log

def selections(d,c):
    rows=[]
    for _,r in d.loc[d[c].notna(),['response_id',c]].iterrows():
        for item in dict.fromkeys(x.strip() for x in str(r[c]).split(',') if x.strip()):
            rows.append({'response_id':r['response_id'],'option':item})
    return pd.DataFrame(rows,columns=['response_id','option']).drop_duplicates()

def counts(d,c,multi=False,order=None):
    n=int(d[c].notna().sum()); missing=len(d)-n
    s=selections(d,c)['option'].value_counts() if multi else d[c].value_counts()
    if order is not None: s=s.reindex(list(dict.fromkeys(order+list(s.index))),fill_value=0)
    else: s=s.sort_values()
    t=s.rename_axis('option').reset_index(name='count')
    t['percent']=t['count']/n*100 if n else 0.
    t['valid_n']=n; t['missing_n']=missing
    return t

def themes(d,c):
    valid=d[d[c].map(substantive)]
    rows=[]
    for _,r in valid.iterrows():
        hit=False
        for theme,pattern in THEMES.items():
            if re.search(pattern,str(r[c]),re.I): rows.append((r.response_id,theme));hit=True
        if not hit: rows.append((r.response_id,'Other / needs review'))
    return pd.DataFrame(rows,columns=['response_id','theme']).drop_duplicates(),valid
