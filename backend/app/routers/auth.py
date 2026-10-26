from fastapi import APIRouter, Depends, HTTPException, status

from .. import db
from ..deps import USER_COLS, get_current_user
from ..schemas import LoginIn, MeUpdate, RegisterIn, TokenOut, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Kimlik doğrulama"])


def _token_out(user: dict) -> TokenOut:
    return TokenOut(access_token=create_access_token(user["id"], user["role"]), user=UserOut(**user))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED, summary="Kayıt ol")
def register(body: RegisterIn):
    email = body.email.lower().strip()
    username = body.username.strip()
    if db.fetch_one("SELECT 1 FROM users WHERE email = %s", (email,)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu e-posta ile kayıtlı bir hesap zaten var")
    if db.fetch_one("SELECT 1 FROM users WHERE lower(username) = lower(%s)", (username,)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu kullanıcı adı alınmış")
    user = db.fetch_one(
        f"""INSERT INTO users (email, username, full_name, password_hash, organization)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING {USER_COLS}""",
        (email, username, body.full_name.strip() or username, hash_password(body.password),
         (body.organization or "").strip() or None),
    )
    return _token_out(user)


@router.post("/login", response_model=TokenOut, summary="Giriş yap (e-posta veya kullanıcı adı ile JWT al)")
def login(body: LoginIn):
    ident = body.email.strip()
    row = db.fetch_one(
        f"SELECT {USER_COLS}, password_hash FROM users WHERE email = lower(%s) OR lower(username) = lower(%s)",
        (ident, ident),
    )
    if not row or not verify_password(body.password, row.pop("password_hash")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-posta veya şifre hatalı")
    return _token_out(row)


@router.get("/me", response_model=UserOut, summary="Oturumdaki kullanıcı")
def me(user: dict = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut, summary="Profili güncelle (kullanıcı adı, ad soyad)")
def update_me(body: MeUpdate, user: dict = Depends(get_current_user)):
    data = body.model_dump(exclude_none=True)
    if "username" in data:
        data["username"] = data["username"].strip()
        clash = db.fetch_one(
            "SELECT 1 FROM users WHERE lower(username) = lower(%s) AND id <> %s", (data["username"], user["id"])
        )
        if clash:
            raise HTTPException(status.HTTP_409_CONFLICT, "Bu kullanıcı adı alınmış")
    if data:
        sets = ", ".join(f"{k} = %({k})s" for k in data)
        db.execute(f"UPDATE users SET {sets} WHERE id = %(id)s", {**data, "id": user["id"]})
    return db.fetch_one(f"SELECT {USER_COLS} FROM users WHERE id = %s", (user["id"],))
