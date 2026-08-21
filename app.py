
import streamlit as st
import cv2, numpy as np, pandas as pd
from PIL import Image
from io import BytesIO
from urllib.parse import quote
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

SCHOOL="PM SHRI जिल्हा परिषद केंद्रीय मराठी उच्च प्राथमिक शाळा, वेणी"
N=40; OPTIONS="ABCD"

st.set_page_config(page_title="PM SHRI Smart OMR",page_icon="📝",layout="wide")

def make_omr(exam, cls, subject, key):
    buf=BytesIO(); c=canvas.Canvas(buf,pagesize=A4); w,h=A4
    c.setFont("Helvetica-Bold",14); c.drawCentredString(w/2,h-15*mm,"PM SHRI SMART OMR")
    c.setFont("Helvetica",9); c.drawCentredString(w/2,h-21*mm,SCHOOL)
    c.setFont("Helvetica-Bold",10); c.drawString(12*mm,h-31*mm,f"परीक्षा: {exam}   इयत्ता: {cls}   विषय: {subject}")
    c.drawString(12*mm,h-39*mm,"विद्यार्थ्याचे नाव: ______________________________________________")
    c.drawString(145*mm,h-39*mm,"रोल नं.: __________")
    # fixed registration squares
    for x,y in [(12,h-48*mm),(198*mm,h-48*mm),(12,12*mm),(198*mm,12*mm)]:
        c.rect(x,y,6*mm,6*mm,fill=1)
    y=h-58*mm
    for i in range(N):
        c.setFont("Helvetica-Bold",8); c.drawString(15*mm,y,f"{i+1:02d}")
        for j,L in enumerate(OPTIONS):
            x=(40+j*22)*mm
            c.circle(x,y+1.2*mm,3.2*mm); c.setFont("Helvetica",7); c.drawCentredString(x,y-1*mm,L)
        y-=6.6*mm
    c.setFont("Helvetica",7); c.drawString(12*mm,7*mm,"प्रत्येक प्रश्नासाठी एकच वर्तुळ पूर्णपणे काळे करा. OMR शीट वाकवू नका.")
    c.save(); buf.seek(0); return buf

def rectify(img):
    gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    edge=cv2.Canny(cv2.GaussianBlur(gray,(5,5),0),50,150)
    cnts,_=cv2.findContours(edge,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(cnts,key=cv2.contourArea,reverse=True)[:30]:
        peri=cv2.arcLength(c,True); ap=cv2.approxPolyDP(c,.02*peri,True)
        if len(ap)==4 and cv2.contourArea(ap)>img.shape[0]*img.shape[1]*.30:
            p=ap.reshape(4,2).astype("float32")
            s=p.sum(1); d=np.diff(p,axis=1).ravel()
            p=np.array([p[np.argmin(s)],p[np.argmin(d)],p[np.argmax(s)],p[np.argmax(d)]],dtype="float32")
            dst=np.array([[0,0],[999,0],[999,1409],[0,1409]],dtype="float32")
            M=cv2.getPerspectiveTransform(p,dst)
            return cv2.warpPerspective(img,M,(1000,1410))
    return None

def read_omr(warped):
    gray=cv2.cvtColor(warped,cv2.COLOR_BGR2GRAY)
    gray=cv2.GaussianBlur(gray,(5,5),0)
    ans=[]; confidence=[]
    for i in range(N):
        y=315+i*27 # fixed generated layout, scaled to 1410 px
        scores=[]
        for j in range(4):
            x=220+j*170
            roi=gray[max(0,y-14):y+15,max(0,x-14):x+15]
            scores.append(255-float(np.mean(roi)))
        order=np.argsort(scores)[::-1]
        best,second=order[0],order[1]
        if scores[best]<28: a=""
        elif scores[best]-scores[second]<4: a="?"
        else: a=OPTIONS[best]
        ans.append(a); confidence.append(round(scores[best],1))
    return ans,confidence

def result_pdf(student, roll, exam, cls, subject, df, score):
    buf=BytesIO(); c=canvas.Canvas(buf,pagesize=A4); w,h=A4
    c.setFont("Helvetica-Bold",13); c.drawCentredString(w/2,h-18*mm,SCHOOL)
    c.setFont("Helvetica-Bold",12); c.drawCentredString(w/2,h-27*mm,"विद्यार्थी निकाल")
    c.setFont("Helvetica",10)
    c.drawString(15*mm,h-38*mm,f"विद्यार्थी: {student}   रोल नं.: {roll}")
    c.drawString(15*mm,h-45*mm,f"परीक्षा: {exam}   इयत्ता: {cls}   विषय: {subject}")
    c.setFont("Helvetica-Bold",16); c.drawString(15*mm,h-58*mm,f"गुण: {score}/{len(df)}   टक्केवारी: {score/len(df)*100:.1f}%")
    y=h-70*mm; c.setFont("Helvetica",8)
    for _,r in df.iterrows():
        c.drawString(15*mm,y,f"{int(r['प्रश्न'])}. योग्य: {r['योग्य उत्तर']}  आढळले: {r['आढळलेले उत्तर']}  {r['स्थिती']}")
        y-=5*mm
        if y<12*mm: c.showPage(); y=h-15*mm
    c.save(); buf.seek(0); return buf

st.title("📝 PM SHRI Smart OMR")
st.caption(SCHOOL)

with st.sidebar:
    st.header("1️⃣ परीक्षा सेटअप")
    exam=st.text_input("परीक्षेचे नाव","घटक चाचणी")
    cls=st.text_input("इयत्ता","४ थी")
    subject=st.text_input("विषय","इंग्रजी")
    teacher=st.text_input("शिक्षकाचे नाव","")
    st.subheader("उत्तरतालिका")
    key=[]
    cols=st.columns(4)
    for i in range(N):
        with cols[i%4]:
            key.append(st.selectbox(str(i+1),list(OPTIONS),key=f"key{i}"))

st.header("2️⃣ OMR Sheet तयार करा")
st.download_button("🖨️ OMR Sheet PDF डाउनलोड/Print",make_omr(exam,cls,subject,key),"PM_SHRI_OMR.pdf","application/pdf")

st.header("3️⃣ विद्यार्थी माहिती")
c1,c2=st.columns(2)
student=c1.text_input("विद्यार्थ्याचे नाव")
roll=c2.text_input("रोल नंबर")

st.header("4️⃣ 📷 OMR Scan → Automatic Checking")
source=st.camera_input("मोबाईल कॅमेऱ्याने OMR स्कॅन करा")
upload=st.file_uploader("किंवा OMR फोटो upload करा",type=["jpg","jpeg","png"])
source=source or upload

if source:
    arr=np.frombuffer(source.getvalue(),np.uint8); img=cv2.imdecode(arr,cv2.IMREAD_COLOR)
    warped=rectify(img)
    if warped is None:
        st.error("OMR शीटची चौकट सापडली नाही. पूर्ण शीट सरळ व चारही कोपरे दिसतील अशी पुन्हा scan करा.")
    elif st.button("⚡ Automatic Check & Result"):
        detected,conf=read_omr(warped)
        rows=[]; correct=0; wrong=0; blank=0; uncertain=0
        for i,(k,a) in enumerate(zip(key,detected),1):
            if a=="": status="अनुत्तरित"; blank+=1
            elif a=="?": status="अस्पष्ट/दुहेरी"; uncertain+=1
            elif a==k: status="बरोबर"; correct+=1
            else: status="चूक"; wrong+=1
            rows.append([i,k,a,status,conf[i-1]])
        df=pd.DataFrame(rows,columns=["प्रश्न","योग्य उत्तर","आढळलेले उत्तर","स्थिती","विश्वास"])
        st.session_state["df"]=df; st.session_state["score"]=correct
        st.success(f"निकाल तयार — {correct}/{N} ({correct/N*100:.1f}%)")
        st.dataframe(df,use_container_width=True,hide_index=True)

if "df" in st.session_state:
    df=st.session_state["df"]; score=st.session_state["score"]
    st.header("5️⃣ 🏆 Result & WhatsApp")
    st.metric("गुण",f"{score}/{N}",f"{score/N*100:.1f}%")
    pdf=result_pdf(student,roll,exam,cls,subject,df,score)
    st.download_button("📄 Student Result PDF",pdf,"student_result.pdf","application/pdf")
    csv=df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📊 Excel-compatible CSV",csv,"result.csv","text/csv")
    phone=st.text_input("WhatsApp नंबर (country code सहित, उदा. 9198XXXXXXXX)")
    msg=f"""PM SHRI जिल्हा परिषद केंद्रीय मराठी उच्च प्राथमिक शाळा, वेणी
परीक्षा: {exam}
इयत्ता: {cls} | विषय: {subject}
विद्यार्थी: {student}
रोल नं.: {roll}
निकाल: {score}/{N} ({score/N*100:.1f}%)
"""
    if phone:
        url="https://wa.me/"+phone.replace("+","").replace(" ","")+"?text="+quote(msg)
        st.link_button("💬 WhatsApp वर निकाल पाठवा",url)
    st.info("टीप: हा WhatsApp button शिक्षकाच्या WhatsApp मधून तयार संदेश पाठवतो. पूर्णपणे automatic API sending साठी Meta WhatsApp Business API credentials आवश्यक आहेत.")
