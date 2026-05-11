import os
import uuid
import streamlit as st
from langgraph.types import Command

# Bật tính năng interrupt của LangGraph (chặn lại chờ người duyệt)
os.environ["LANGGRAPH_INTERRUPT"] = "true"

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import initial_state, Scenario, Route

st.set_page_config(page_title="Support Ticket Agent", page_icon="🤖", layout="centered")

st.title("🤖 Support Ticket Agent")
st.markdown("---")

@st.cache_resource
def get_graph():
    # Khởi tạo graph với SQLite checkpointer để nhớ trạng thái sau mỗi lần reload giao diện
    checkpointer = build_checkpointer("sqlite", "checkpoints.db")
    return build_graph(checkpointer=checkpointer)

graph = get_graph()

# Cấp phát 1 ID hội thoại mới cho mỗi user session
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

thread_config = {"configurable": {"thread_id": st.session_state.thread_id}}

# Lưu lại log hội thoại trên màn hình
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Kiểm tra xem AI có đang bị "chặn" lại ở Approval Node không?
current_state = graph.get_state(thread_config)
is_interrupted = len(current_state.tasks) > 0 and current_state.tasks[0].interrupts

if is_interrupted:
    # Lấy data do Agent gửi ra để xin duyệt
    interrupt_data = current_state.tasks[0].interrupts[0].value
    
    st.error("⚠️ **HỆ THỐNG CẦN XÁC NHẬN TỪ QUẢN TRỊ VIÊN**")
    with st.container(border=True):
        st.write(f"**Hành động đề xuất:** {interrupt_data.get('proposed_action')}")
        st.write(f"**Mức độ rủi ro:** `{interrupt_data.get('risk_level').upper()}`")
        
        with st.form("approval_form"):
            comment = st.text_input("Nhập ghi chú cho Agent (Reviewer Comment):", value="Đồng ý thực hiện")
            col1, col2 = st.columns(2)
            with col1:
                approve = st.form_submit_button("✅ Đồng Ý (Approve)", type="primary", use_container_width=True)
            with col2:
                reject = st.form_submit_button("❌ Từ Chối (Reject)", use_container_width=True)
                
            if approve or reject:
                # Trả lại quyết định cho Agent
                decision = {
                    "approved": bool(approve),
                    "comment": comment,
                    "reviewer": "Admin"
                }
                with st.spinner("Đang resume lại workflow..."):
                    # Command(resume=decision) sẽ truyền dữ liệu vào node bị chặn
                    final_state = graph.invoke(Command(resume=decision), config=thread_config)
                    
                    final_answer = final_state.get("final_answer") or final_state.get("pending_question")
                    if final_answer:
                        st.session_state.messages.append({"role": "assistant", "content": final_answer})
                        st.rerun()

else:
    # Nhập câu hỏi từ user
    if prompt := st.chat_input("Nhập câu hỏi (Thử gõ: 'tôi muốn hoàn tiền' hoặc 'refund order 123'):"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            with st.spinner("Agent đang suy nghĩ và chạy đồ thị..."):
                # Gói prompt vào cấu trúc Scenario của bài lab
                scenario = Scenario(id="streamlit_user", query=prompt, expected_route=Route.SIMPLE)
                state = initial_state(scenario)
                state["thread_id"] = st.session_state.thread_id
                
                # Chạy Agent
                new_state = graph.invoke(state, config=thread_config)
                
                # Check lại xem đồ thị có rẽ vào luồng rủi ro và bị ngắt không
                current_state_after = graph.get_state(thread_config)
                if len(current_state_after.tasks) > 0 and current_state_after.tasks[0].interrupts:
                    st.rerun() # Refresh lại để hiện UI Approval
                else:
                    final_answer = new_state.get("final_answer") or new_state.get("pending_question")
                    if final_answer:
                        st.markdown(final_answer)
                        st.session_state.messages.append({"role": "assistant", "content": final_answer})
                    else:
                        st.markdown("Không có phản hồi từ Agent.")

# Nút dọn dẹp
with st.sidebar:
    st.subheader("Cài đặt Session")
    if st.button("Làm mới đoạn chat"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()
