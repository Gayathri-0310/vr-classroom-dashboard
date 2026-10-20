from pathlib import Path
import io, json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from survey_core import *

st.set_page_config(page_title='Beyond Slides',page_icon='🥽',layout='wide')
st.sidebar.title('Beyond Slides')
upload=st.sidebar.file_uploader('Upload survey workbook',type=['xlsx'])
try:
    source=io.BytesIO(upload.getvalue()) if upload else Path(__file__).with_name('survey_cleaned.xlsx')
    full,cleaning_log=load_book(source)
except Exception as e:
    st.error(f'Cannot read workbook: {e}'); st.stop()
light=st.sidebar.toggle('Light mode',value=False)
bg,card,fg=('#f3f6fb','#ffffff','#142438') if light else ('#091323','#12213a','#edf5ff')
st.markdown(f'''<style>
.stApp {{background:{bg};color:{fg}}}
[data-testid="stSidebar"] {{border-right:1px solid #49607855}}
h1,h2,h3,p,label,[data-testid="stMetricValue"],[data-testid="stMetricLabel"] {{color:{fg}!important}}
[data-testid="stMetric"] {{background:{card};border:1px solid #4b708855;border-radius:16px;padding:18px;transition:transform .2s}}
[data-testid="stMetric"]:hover {{transform:translateY(-2px)}}
[data-testid="stMetricValue"] {{font-size:1.8rem;color:#29c9b5!important}}
.stButton button,.stDownloadButton button {{border-radius:12px}}
@media(max-width:700px) {{h1 {{font-size:1.8rem!important}}}}
</style>''',unsafe_allow_html=True)
PAGES=['Overview','Current Learning','VR Readiness','Pilot Planning','Student Voice','Data Notes']
page=st.sidebar.radio('Explore',PAGES)
mode=st.sidebar.radio('Chart measure',['Percentage','Count'],horizontal=True)

def reset():
    for key in list(st.session_state):
        if key.startswith('flt_'): del st.session_state[key]
st.sidebar.button('Clear all filters',on_click=reset,use_container_width=True)
d=full.copy(); active=[]
for c,title in [('programme','Programme'),('gender','Gender'),('experience','Previous VR experience'),('support','VR support'),('pay','Willingness to pay')]:
    opts=sorted(full[c].fillna('(Missing)').astype(str).unique())
    key='flt_'+c
    if key in st.session_state:
        st.session_state[key]=[v for v in st.session_state[key] if v in opts]
    sel=st.sidebar.multiselect(title,opts,key=key,placeholder='All responses')
    if sel:
        d=d[d[c].fillna('(Missing)').astype(str).isin(sel)]; active.append(title+': '+', '.join(sel))
valid_dates=full.timestamp.dropna()
if not valid_dates.empty:
    use_dates=st.sidebar.checkbox('Filter submission date',key='flt_dates_on')
    if use_dates:
        dates=st.sidebar.date_input('Submission range',value=(valid_dates.min().date(),valid_dates.max().date()),min_value=valid_dates.min().date(),max_value=valid_dates.max().date(),key='flt_dates')
        if len(dates)==2:
            d=d[d.timestamp.dt.date.between(*dates)];active.append(f'Dates: {dates[0]} to {dates[1]}')
st.title('Beyond Slides: VR Classroom Survey Insights')
st.caption('Exploring student experiences, VR readiness, and classroom innovation.')
st.caption(f'{len(d)} of {len(full)} responses • '+(' | '.join(active) if active else 'All responses · no active filters'))
st.sidebar.caption('All charts share these filters. Empty selections mean all values. Plotly legend clicks affect only that chart; cross-chart point selection is not enabled.')
if d.empty: st.warning('No responses match these filters. Clear filters or choose a broader group.');st.stop()
if len(d)<5: st.warning('Small filtered group (n < 5): treat summaries as exploratory. Share exports cautiously.')
colors=['#27cdb2','#48bdf4','#9b87f5','#f5c36b','#ed8297','#7ba6bc']
template='plotly_white' if light else 'plotly_dark'
counter=0
figures=[]
def show(fig,title):
    global counter
    counter+=1
    fig.update_layout(template=template,paper_bgcolor=card,plot_bgcolor=card,font=dict(family='Arial',color=fg),title=dict(text=title,font_size=17),margin=dict(l=15,r=15,t=55,b=35),height=370,legend_title_text='')
    fig.update_xaxes(gridcolor='#6c859622');fig.update_yaxes(gridcolor='#6c859622')
    figures.append((title,fig))
    st.plotly_chart(fig,use_container_width=True,key='plot_'+str(counter),config={'displaylogo':False,'toImageButtonOptions':{'format':'png','scale':2}})

def bars(c,title,multi=False,order=None):
    t=counts(d,c,multi,order)
    if t.empty or not t.valid_n.iloc[0]: st.info(title+': no valid responses.');return
    y='percent' if mode=='Percentage' else 'count'
    fig=px.bar(t,x=y,y='option',orientation='h',text=t[y].map(lambda v:f'{v:.1f}%' if y=='percent' else str(int(v))),color_discrete_sequence=[colors[0]],custom_data=['count','percent','valid_n','missing_n'])
    fig.update_traces(hovertemplate='%{y}<br>Count: %{customdata[0]}<br>Percent: %{customdata[1]:.1f}%<br>Valid n: %{customdata[2]}<br>Missing: %{customdata[3]}<extra></extra>',cliponaxis=False)
    fig.update_layout(xaxis_title='Percent of valid respondents' if y=='percent' else 'Respondents',yaxis_title='',yaxis=dict(categoryorder='array',categoryarray=t.option.tolist()))
    if order: fig.update_yaxes(autorange='reversed')
    show(fig,title)
    st.caption(f'Valid n={t.valid_n.iloc[0]} · Missing={t.missing_n.iloc[0]}'+(' · Multiple selections allowed; percentages may exceed 100%.' if multi else ''))

def distribution(cols,title):
    rows=[]
    for c in cols:
        n=int(d[c].notna().sum())
        if not n: continue
        for r in range(1,6):
            count=int(d[c].eq(r).sum());rows.append(dict(question=LABELS[c],rating=str(r),count=count,percent=count/n*100,valid_n=n,missing_n=len(d)-n))
    if not rows: st.info('No valid ratings for this selection.');return
    t=pd.DataFrame(rows)
    fig=px.bar(t,x='percent',y='question',color='rating',orientation='h',barmode='stack',category_orders={'rating':['1','2','3','4','5']},color_discrete_map=dict(zip(['1','2','3','4','5'],['#df7183','#e9ab77','#8c9eb6','#4cbbd2','#27cdb2'])),custom_data=['count','valid_n','missing_n'])
    fig.update_traces(hovertemplate='%{y}<br>Share: %{x:.1f}%<br>Count: %{customdata[0]}<br>Valid n: %{customdata[1]}<br>Missing: %{customdata[2]}<extra>%{fullData.name}</extra>')
    fig.update_layout(xaxis_title='Percent of valid answers (rating 1–5)',yaxis_title='')
    show(fig,title)
    if st.toggle('Show mean ratings',key='mean_'+title):
        st.dataframe(pd.DataFrame([{'Question':LABELS[c],'Mean':d[c].mean(),'Valid n':int(d[c].count()),'Missing':int(d[c].isna().sum())} for c in cols]).round(2),hide_index=True,use_container_width=True)

def support_stack(group=None):
    rows=[]
    for name,g in (d.groupby(group,dropna=False) if group else [('All responses',d)]):
        n=int(g.support.notna().sum())
        for answer in ['Yes','Maybe','No']:
            k=int(g.support.eq(answer).sum());rows.append(dict(group=str(name),answer=answer,count=k,percent=k/n*100 if n else 0,valid_n=n,missing_n=len(g)-n))
    t=pd.DataFrame(rows)
    fig=px.bar(t,x='percent',y='group',color='answer',orientation='h',barmode='stack',color_discrete_map={'Yes':'#27cdb2','Maybe':'#8c9eb6','No':'#df7183'},custom_data=['count','valid_n','missing_n'])
    fig.update_traces(hovertemplate='%{y}<br>%{x:.1f}%<br>Count: %{customdata[0]}<br>Valid n: %{customdata[1]}<br>Missing: %{customdata[2]}<extra>%{fullData.name}</extra>')
    fig.update_layout(xaxis_title='Percent of valid support answers',yaxis_title='')
    show(fig,'VR support'+(' by '+group if group else ''))

def theme_view(c,title):
    coded,valid=themes(d,c)
    st.caption(f'Approximate rule-based themes · {len(valid)} substantive responses coded · {len(d)-len(valid)} missing/non-substantive. Multiple themes allowed; percentages may exceed 100%.')
    if coded.empty: st.info('No substantive responses to code.');return coded,valid
    t=coded.theme.value_counts().sort_values().rename_axis('theme').reset_index(name='count'); t['percent']=t['count']/len(valid)*100
    y='percent' if mode=='Percentage' else 'count'
    fig=px.bar(t,x=y,y='theme',orientation='h',color_discrete_sequence=[colors[2]],hover_data={'count':True,'percent':':.1f'})
    fig.update_layout(xaxis_title='Percent of substantive responses' if y=='percent' else 'Responses',yaxis_title='')
    show(fig,title)
    return coded,valid

def top(c,multi=False):
    t=counts(d,c,multi)
    if t.empty: return 'No valid responses.'
    r=t.sort_values('count',ascending=False).iloc[0]
    return f'{r.option}: {r["count"]}/{r.valid_n} ({r.percent:.1f}%). Ties are possible; consult the chart.'

st.header(page)
if page=='Overview':
    metrics=[('Responses',str(len(d)),f'Total rows in current filter: {len(d)}'),('VR support','support','Yes'),('Prior VR exposure','experience','exposure'),('Expected VR interest','interest','mean'),('Headset comfort','comfort','mean'),('Willing to pay','pay','Yes')]
    for col,(title,c,kind) in zip(st.columns(6),metrics):
        if title=='Responses': val=c;helptext=kind
        else:
            n=int(d[c].notna().sum())
            if kind=='mean': val=f'{d[c].mean():.2f}/5' if n else 'N/A';helptext=f'{n} valid ratings; {len(d)-n} missing.'
            else:
                k=int((d[c].notna() & d[c].ne('Never')).sum()) if kind=='exposure' else int(d[c].eq(kind).sum())
                val=f'{k/n*100:.1f}%' if n else 'N/A';helptext=f'{k}/{n} valid responses; {len(d)-n} missing.'
                if c=='pay': helptext+=' Conditional: '+str(int(d.pay.eq('Depends on the amount').sum()))+f'/{n}.'
        col.metric(title,val,help=helptext)
    st.caption('Payment conditional on amount: '+top('pay')+' See Pilot Planning for the complete payment distribution.')
    support_stack()
    a,b=st.columns(2)
    with a: bars('activities','Most appealing VR activities',True)
    with b: bars('concerns','Concerns about VR',True)
    bars('programme','Who responded? Programme composition')
    st.subheader('Key findings in this selection')
    st.write('• Most selected activity — '+top('activities',True))
    st.write('• Most selected concern — '+top('concerns',True))
    st.write('• Preferred session length — '+top('duration'))
    st.write('• Preferred frequency — '+top('frequency'))
elif page=='Current Learning':
    a,b=st.columns(2)
    with a: bars('methods','Current learning methods',True)
    with b: bars('disengagement','Reasons for losing interest',True)
    distribution(['practical','relevance','attention','workshops'],'Current classroom experience')
    bars('real_life','“I will never use this in real life”',order=['Never','Sometimes','Often','Always'])
    theme_view('difficult_subject','Themes in difficult or unengaging subjects')
    st.info('These are current perceptions. Expected VR ratings are not measured post-intervention outcomes.')
elif page=='VR Readiness':
    bars('experience','Previous VR experience',order=['Never','Once or twice','Regularly'])
    distribution(['understanding','interest','concepts','comfort','retention','placement'],'VR expectations and comfort')
    support_stack('experience')
    support_stack('programme')
    st.subheader('Programme comparisons')
    comparison=d.groupby('programme',dropna=False).agg(Responses=('response_id','size'),Interest=('interest','mean'),Interest_n=('interest','count'),Comfort=('comfort','mean'),Comfort_n=('comfort','count'))
    comparison['Small group']=comparison.Responses.lt(5)
    st.dataframe(comparison.round(2),use_container_width=True)
    st.subheader('Headset comfort by prior experience')
    comfort=d.groupby('experience',dropna=False).comfort.agg(['mean','count']).rename(columns={'count':'Valid n','mean':'Mean comfort'})
    st.dataframe(comfort.round(2),use_container_width=True)
    st.subheader('Current practical exposure and VR support')
    relationship=d.groupby('support',dropna=False).practical.agg(['mean','count']).rename(columns={'mean':'Mean current practical exposure','count':'Valid n'})
    st.dataframe(relationship.round(2),use_container_width=True)
    st.caption('Descriptive comparisons only. Subgroups with n < 5 require caution. No causal effect, statistical significance, or composite readiness score is claimed.')
elif page=='Pilot Planning':
    a,b=st.columns(2)
    with a: bars('duration','Preferred session length',order=['15 min','30 min','45 min','Full Period'])
    with b: bars('frequency','Preferred frequency',order=['Weekly','Fortnightly','Monthly','Only for selected topics'])
    bars('pay','Willingness to pay',order=['Yes','Depends on the amount','No'])
    a,b=st.columns(2)
    with a: bars('activities','Activity interest',True)
    with b: bars('concerns','Implementation concerns',True)
    theme_view('benefit_subject','Subjects and topics suggested for VR')
    st.subheader('Pilot planning signals')
    for c in ['duration','frequency','activities','concerns']: st.write('• '+c.capitalize()+' — '+top(c,c in MULTI))
    st.subheader('Explore a combined pilot preference')
    opts={c:sorted(d[c].dropna().astype(str).unique()) for c in ['duration','frequency']}
    activity_opts=sorted(selections(d,'activities').option.unique())
    if all(opts.values()) and activity_opts:
        a,b,c=st.columns(3)
        duration=a.selectbox('Session length',opts['duration']);frequency=b.selectbox('Frequency',opts['frequency']);activity=c.selectbox('Activity',activity_opts)
        valid=d[['duration','frequency','activities']].notna().all(axis=1)
        ids=set(selections(d,'activities').query('option == @activity').response_id)
        k=int((valid & d.duration.eq(duration)&d.frequency.eq(frequency)&d.response_id.isin(ids)).sum());n=int(valid.sum())
        st.metric('Respondents selecting all three',f'{k}/{n}',help='Denominator: respondents with all three questions answered.')
        st.caption(f'{k/n*100:.1f}% of complete answers; {len(d)-n} excluded for missing answers.' if n else 'No complete answers.')
    st.info('Pilot signals are exploratory. Separate popular choices do not prove preference for their combination. The survey gives no acceptable fee amount and does not establish learning gains.')
elif page=='Student Voice':
    c=st.selectbox('Question',['difficult_subject','benefit_subject','suggestions'],format_func=lambda k:{'difficult_subject':'Difficult / unengaging subjects','benefit_subject':'Subjects that could benefit from VR','suggestions':'Suggestions for practical classes'}[k])
    coded,valid=theme_view(c,'Student voice themes')
    query=st.text_input('Search anonymous responses (literal text)')
    browser=valid[['response_id',c]].copy()
    if not coded.empty:
        lookup=coded.groupby('response_id').theme.agg(' | '.join)
        browser['Approximate themes']=browser.response_id.map(lookup)
    if query: browser=browser[browser[c].str.contains(query,case=False,regex=False,na=False)]
    st.dataframe(browser,hide_index=True,use_container_width=True)
    st.caption('Browser omits programme/gender to reduce re-identification. IDs are pseudonymous, not a guarantee against re-identification. Avoid public release of small-group comments without manual review.')
    st.subheader('Illustrative anonymous comments')
    st.caption('Deterministic examples: one short comment from each of up to three different themes; illustrative, not a statistically representative sample.')
    used=set()
    if not coded.empty:
        for theme in coded.theme.value_counts().index:
            pool=valid[valid.response_id.isin(coded.loc[coded.theme.eq(theme),'response_id']) & ~valid.response_id.isin(used)]
            if pool.empty: continue
            r=pool.loc[pool[c].str.len().sort_values().index].iloc[0]
            st.write(f'{r.response_id} · {theme}');st.info(str(r[c]));used.add(r.response_id)
            if len(used)>=3: break
else:
    st.subheader('Cleaning log')
    for line in cleaning_log: st.write('• '+line)
    st.subheader('Methods and limitations')
    st.markdown('''- Each question uses its own valid-response denominator; missing values are not zero.
- Ratings use integers 1–5. Strongly disagree=1, Disagree=2, Neutral=3, Agree=4, Strongly agree=5. Unrecognized/out-of-range ratings become missing.
- Only four known multi-select questions are split on commas. Counts represent distinct respondents per option. Open-ended text is never comma-split.
- Multi-select percentages can total over 100%. “None” is retained as an explicit concern response, not counted as missing or silently dropped.
- Theme coding uses transparent keyword rules, permits multiple themes, and needs review. Non-substantive open text is excluded only from thematic analysis.
- Similar answers are not automatically deleted. Suspected duplicate flags are retained for review.
- Results describe surveyed respondents, not necessarily the college population. Small groups (n < 5) are flagged; this threshold is a display caution, not a statistical test.
- The survey measures opinions and expectations, not causal learning improvements. No inference, composite readiness score, fee estimate, revenue forecast, or trend claim is made.
- Raw email and placeholder columns are excluded. Automatic text redaction is imperfect: manually review text before external sharing. Structured exports below exclude written comments, exact timestamps, and demographic combinations by default.
- All sidebar filters affect all analyses. Charts support hover, zoom, local legend selection, and PNG export; cross-chart point filtering is not implemented.
''')
    st.subheader('Transparent theme rules')
    st.dataframe(pd.DataFrame(THEMES.items(),columns=['Theme','Regex rule']),hide_index=True,use_container_width=True)
    st.subheader('Data dictionary and completeness (current filters)')
    reverse={v:k for k,v in COLUMN_MAP.items()}
    dictionary=pd.DataFrame([{'Field':c,'Survey question':reverse.get(c,c),'Type':'rating 1–5' if c in RATINGS else 'multi-select' if c in MULTI else 'open text' if c in TEXT else str(d[c].dtype),'Valid n':int(d[c].count()),'Missing':int(d[c].isna().sum())} for c in d])
    st.dataframe(dictionary,hide_index=True,use_container_width=True)
    st.subheader('Duplicate review')
    flagged=d.loc[d.duplicate_review,['response_id','duplicate_review']]
    st.dataframe(flagged,hide_index=True)

st.divider()
st.subheader('Export this selection')
# Default row-level export omits demographics, exact dates, and written comments.
export=d.drop(columns=TEXT+['timestamp','programme','programme_original','gender'],errors='ignore')
st.download_button('Download filtered anonymous CSV',export.to_csv(index=False).encode('utf-8'),'filtered_survey.csv','text/csv')
st.caption('CSV contains anonymous response IDs and structured answers, not emails, demographics, exact dates, or written comments. Re-identification risk is not zero; review before sharing.')
report={'page':page,'responses':len(d),'filters':active,'notes':'Descriptive survey only. Question-specific valid denominators. Multiple selections allowed. No causal inference.','results':{c:counts(d,c,c in MULTI).to_dict(orient='records') for c in ['support','experience','pay','duration','frequency']+MULTI},'rating_summary':{c:{'mean':None if pd.isna(d[c].mean()) else round(float(d[c].mean()),2),'valid_n':int(d[c].count()),'missing_n':int(d[c].isna().sum())} for c in RATINGS}}
st.download_button('Download aggregate report (JSON)',json.dumps(report,indent=2,default=str),'survey_summary.json','application/json')
if figures:
    import plotly.io as pio
    html='<html><head><meta charset="utf-8"><title>Beyond Slides — exported charts</title></head><body><h1>Beyond Slides</h1><p>Filtered responses: '+str(len(d))+'. Descriptive survey only. This export is a chart snapshot; use the app for linked filters.</p>'
    for i,(title,fig) in enumerate(figures): html+=pio.to_html(fig,full_html=False,include_plotlyjs=True if i==0 else False)
    html+='</body></html>'
    st.download_button('Download page charts (offline HTML)',html,'survey_charts.html','text/html')
