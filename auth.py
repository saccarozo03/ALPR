import streamlit as st

def is_logged_in() -> bool:
    return st.session_state.get("logged_in", False)

def render_login(users: dict) -> None:
    u = st.text_input("Username", key="login_username")
    p = st.text_input("Password", type="password", key="login_password")

    if st.button("Login", key="btn_login"):
        if u in users and users[u] == p:
            st.session_state["logged_in"] = True
            st.session_state["username"] = u
            st.success("Đăng nhập thành công.")
            st.rerun()
        else:
            st.error("Sai tài khoản/mật khẩu.")

    st.stop()

def render_logout() -> None:
    if st.button("Logout", key="btn_logout"):
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.rerun()
