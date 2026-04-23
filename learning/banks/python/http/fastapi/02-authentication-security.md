# Module 2: Authentication & Security

---

## 2.1 Authentication Mechanisms

### OAuth2 Password Flow

```python
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Annotated
from datetime import datetime, timedelta
import hashlib
import secrets

app = FastAPI()

# OAuth2 scheme - specifies the token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Fake user database
fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "email": "john@example.com",
        "hashed_password": "hashed_secret123",
        "disabled": False
    }
}

class User(BaseModel):
    username: str
    email: str | None = None
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str

def hash_password(password: str) -> str:
    """Simple hash for demo - use proper hashing in production"""
    return "hashed_" + password

def verify_password(plain: str, hashed: str) -> bool:
    return hash_password(plain) == hashed

def get_user(db: dict, username: str) -> UserInDB | None:
    if username in db:
        return UserInDB(**db[username])
    return None

def authenticate_user(db: dict, username: str, password: str) -> UserInDB | None:
    user = get_user(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

# Token storage (use Redis in production)
tokens_db: dict[str, dict] = {}

def create_access_token(username: str, expires_delta: timedelta) -> str:
    token = secrets.token_urlsafe(32)
    expire = datetime.utcnow() + expires_delta
    tokens_db[token] = {"username": username, "expires": expire}
    return token

def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    if token not in tokens_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token_data = tokens_db[token]
    if datetime.utcnow() > token_data["expires"]:
        del tokens_db[token]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )

    user = get_user(fake_users_db, token_data["username"])
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

CurrentUser = Annotated[User, Depends(get_current_active_user)]

@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = create_access_token(
        username=user.username,
        expires_delta=timedelta(minutes=30)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
async def read_users_me(current_user: CurrentUser):
    return current_user

@app.get("/protected")
async def protected_route(current_user: CurrentUser):
    return {"message": f"Hello {current_user.username}"}
```

### JWT Token Creation and Validation

```python
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Annotated
import jwt
from passlib.context import CryptContext

app = FastAPI()

# Configuration
SECRET_KEY = "your-secret-key-here-use-env-variable"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None
    exp: datetime | None = None

class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str

# Password utilities
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# JWT utilities
def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return TokenData(username=username, exp=payload.get("exp"))
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Fake database
fake_users_db = {
    "johndoe": UserInDB(
        username="johndoe",
        email="john@example.com",
        full_name="John Doe",
        hashed_password=get_password_hash("secret"),
        disabled=False
    )
}

def authenticate_user(username: str, password: str) -> UserInDB | None:
    user = fake_users_db.get(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)]
) -> User:
    token_data = decode_token(token)
    user = fake_users_db.get(token_data.username)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]

@app.post("/token", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: CurrentUser):
    return current_user
```

### Refresh Token Rotation

```python
from fastapi import FastAPI, Depends, HTTPException, status, Response, Cookie
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Annotated
import jwt
import secrets
import hashlib

app = FastAPI()

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Refresh token storage (use database in production)
refresh_tokens_db: dict[str, dict] = {}

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

def create_access_token(user_id: str, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "access"},
        SECRET_KEY,
        algorithm=ALGORITHM
    )

def create_refresh_token(user_id: str) -> str:
    """Create and store refresh token"""
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    refresh_tokens_db[token_hash] = {
        "user_id": user_id,
        "expires": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "created": datetime.now(timezone.utc)
    }
    return token

def verify_refresh_token(token: str) -> str | None:
    """Verify refresh token and return user_id"""
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    if token_hash not in refresh_tokens_db:
        return None

    token_data = refresh_tokens_db[token_hash]
    if datetime.now(timezone.utc) > token_data["expires"]:
        del refresh_tokens_db[token_hash]
        return None

    return token_data["user_id"]

def revoke_refresh_token(token: str):
    """Revoke a refresh token"""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    refresh_tokens_db.pop(token_hash, None)

def revoke_all_user_tokens(user_id: str):
    """Revoke all refresh tokens for a user"""
    to_delete = [
        h for h, data in refresh_tokens_db.items()
        if data["user_id"] == user_id
    ]
    for h in to_delete:
        del refresh_tokens_db[h]


@app.post("/token", response_model=TokenPair)
async def login(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    # Authenticate user (simplified)
    user_id = form_data.username

    # Create token pair
    access_token = create_access_token(
        user_id,
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_refresh_token(user_id)

    # Set refresh token as HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@app.post("/token/refresh", response_model=Token)
async def refresh_access_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None)
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token required")

    user_id = verify_refresh_token(refresh_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Rotate refresh token (revoke old, create new)
    revoke_refresh_token(refresh_token)
    new_refresh_token = create_refresh_token(user_id)

    # Create new access token
    access_token = create_access_token(
        user_id,
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Update cookie with new refresh token
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@app.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None)
):
    if refresh_token:
        revoke_refresh_token(refresh_token)

    response.delete_cookie("refresh_token")
    return {"message": "Logged out"}


@app.post("/logout/all")
async def logout_all_devices(current_user: CurrentUser, response: Response):
    """Revoke all refresh tokens for the user"""
    revoke_all_user_tokens(current_user.id)
    response.delete_cookie("refresh_token")
    return {"message": "Logged out from all devices"}
```

### OAuth2 Scopes

```python
from fastapi import FastAPI, Depends, HTTPException, status, Security
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    SecurityScopes
)
from pydantic import BaseModel
from typing import Annotated
import jwt
from datetime import datetime, timedelta, timezone

app = FastAPI()

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

# Define scopes
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={
        "users:read": "Read user information",
        "users:write": "Create and modify users",
        "items:read": "Read items",
        "items:write": "Create and modify items",
        "admin": "Full administrative access"
    }
)

class Token(BaseModel):
    access_token: str
    token_type: str
    scopes: list[str]

class User(BaseModel):
    username: str
    scopes: list[str] = []

# Fake user with scopes
fake_users_db = {
    "john": User(username="john", scopes=["users:read", "items:read", "items:write"]),
    "admin": User(username="admin", scopes=["admin"])
}

def create_access_token(username: str, scopes: list[str]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    return jwt.encode(
        {"sub": username, "scopes": scopes, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM
    )

async def get_current_user(
    security_scopes: SecurityScopes,
    token: Annotated[str, Depends(oauth2_scheme)]
) -> User:
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value}
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_scopes: list[str] = payload.get("scopes", [])

        if username is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception

    user = fake_users_db.get(username)
    if user is None:
        raise credentials_exception

    # Check if user has required scopes
    # Admin scope grants all permissions
    if "admin" not in token_scopes:
        for scope in security_scopes.scopes:
            if scope not in token_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required scope: {scope}",
                    headers={"WWW-Authenticate": authenticate_value}
                )

    return user


@app.post("/token", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = fake_users_db.get(form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username")

    # Filter requested scopes to those the user has
    requested_scopes = form_data.scopes
    if "admin" in user.scopes:
        granted_scopes = requested_scopes
    else:
        granted_scopes = [s for s in requested_scopes if s in user.scopes]

    access_token = create_access_token(user.username, granted_scopes)

    return Token(
        access_token=access_token,
        token_type="bearer",
        scopes=granted_scopes
    )


# Endpoints with scope requirements
@app.get("/users/me")
async def read_current_user(
    current_user: Annotated[User, Security(get_current_user, scopes=["users:read"])]
):
    return current_user

@app.get("/items")
async def read_items(
    current_user: Annotated[User, Security(get_current_user, scopes=["items:read"])]
):
    return [{"item_id": 1, "name": "Item 1"}]

@app.post("/items")
async def create_item(
    current_user: Annotated[User, Security(get_current_user, scopes=["items:write"])]
):
    return {"item_id": 2, "name": "New Item"}

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: Annotated[User, Security(get_current_user, scopes=["admin"])]
):
    return {"message": f"User {user_id} deleted"}

# Multiple scopes required
@app.put("/items/{item_id}")
async def update_item(
    item_id: int,
    current_user: Annotated[
        User,
        Security(get_current_user, scopes=["items:read", "items:write"])
    ]
):
    return {"item_id": item_id, "message": "Updated"}
```

### API Key Authentication

```python
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, APIKeyQuery, APIKeyCookie
from typing import Annotated
import secrets

app = FastAPI()

# Multiple API key sources
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)
api_key_cookie = APIKeyCookie(name="api_key", auto_error=False)

# Fake API keys database
api_keys_db = {
    "key_abc123": {"user_id": 1, "name": "Production Key", "rate_limit": 1000},
    "key_xyz789": {"user_id": 2, "name": "Development Key", "rate_limit": 100}
}

class APIKey(BaseModel):
    key: str
    user_id: int
    name: str
    rate_limit: int

async def get_api_key(
    api_key_header: str | None = Security(api_key_header),
    api_key_query: str | None = Security(api_key_query),
    api_key_cookie: str | None = Security(api_key_cookie)
) -> APIKey:
    # Check all sources for API key
    api_key = api_key_header or api_key_query or api_key_cookie

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required"
        )

    if api_key not in api_keys_db:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )

    key_data = api_keys_db[api_key]
    return APIKey(key=api_key, **key_data)

ValidAPIKey = Annotated[APIKey, Depends(get_api_key)]

@app.get("/data")
async def get_data(api_key: ValidAPIKey):
    return {
        "message": "Access granted",
        "user_id": api_key.user_id,
        "rate_limit": api_key.rate_limit
    }


# Generate new API keys
@app.post("/api-keys")
async def create_api_key(
    name: str,
    current_user: CurrentUser  # Require authentication
):
    new_key = f"key_{secrets.token_urlsafe(16)}"
    api_keys_db[new_key] = {
        "user_id": current_user.id,
        "name": name,
        "rate_limit": 100
    }
    return {"api_key": new_key, "name": name}


# Revoke API key
@app.delete("/api-keys/{key}")
async def revoke_api_key(key: str, current_user: CurrentUser):
    if key not in api_keys_db:
        raise HTTPException(404, "Key not found")

    key_data = api_keys_db[key]
    if key_data["user_id"] != current_user.id:
        raise HTTPException(403, "Not authorized to revoke this key")

    del api_keys_db[key]
    return {"message": "Key revoked"}
```

### HTTP Basic Authentication

```python
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import Annotated
import secrets

app = FastAPI()

security = HTTPBasic()

# Fake users database
users_db = {
    "john": "secret123",
    "jane": "password456"
}

def verify_credentials(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)]
) -> str:
    # Use constant-time comparison to prevent timing attacks
    is_valid_user = False
    is_valid_pass = False

    if credentials.username in users_db:
        correct_password = users_db[credentials.username]
        is_valid_user = secrets.compare_digest(
            credentials.username.encode("utf8"),
            credentials.username.encode("utf8")
        )
        is_valid_pass = secrets.compare_digest(
            credentials.password.encode("utf8"),
            correct_password.encode("utf8")
        )

    if not (is_valid_user and is_valid_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"}
        )

    return credentials.username

AuthenticatedUser = Annotated[str, Depends(verify_credentials)]

@app.get("/")
async def root(username: AuthenticatedUser):
    return {"message": f"Hello {username}"}


# Optional basic auth (for endpoints that work with or without auth)
def optional_basic_auth(
    credentials: HTTPBasicCredentials | None = Depends(
        HTTPBasic(auto_error=False)
    )
) -> str | None:
    if credentials is None:
        return None

    if credentials.username in users_db:
        if secrets.compare_digest(
            credentials.password.encode(),
            users_db[credentials.username].encode()
        ):
            return credentials.username

    return None

OptionalUser = Annotated[str | None, Depends(optional_basic_auth)]

@app.get("/public")
async def public_route(user: OptionalUser):
    if user:
        return {"message": f"Hello {user}"}
    return {"message": "Hello anonymous"}
```

### Multi-Factor Authentication Patterns

```python
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import Annotated
import pyotp
import secrets
from datetime import datetime, timedelta

app = FastAPI()

# User MFA settings storage
mfa_secrets_db: dict[str, str] = {}
mfa_backup_codes_db: dict[str, list[str]] = {}
pending_mfa_sessions: dict[str, dict] = {}

class MFASetupResponse(BaseModel):
    secret: str
    qr_uri: str
    backup_codes: list[str]

class MFAVerifyRequest(BaseModel):
    session_token: str
    code: str


# MFA Setup
@app.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(current_user: CurrentUser):
    # Generate TOTP secret
    secret = pyotp.random_base32()

    # Create provisioning URI for QR code
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name="MyApp"
    )

    # Generate backup codes
    backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]

    # Store temporarily (user must verify before it's active)
    mfa_secrets_db[f"pending_{current_user.id}"] = secret
    mfa_backup_codes_db[f"pending_{current_user.id}"] = backup_codes

    return MFASetupResponse(
        secret=secret,
        qr_uri=uri,
        backup_codes=backup_codes
    )


@app.post("/mfa/verify-setup")
async def verify_mfa_setup(code: str, current_user: CurrentUser):
    pending_secret = mfa_secrets_db.get(f"pending_{current_user.id}")
    if not pending_secret:
        raise HTTPException(400, "No pending MFA setup")

    totp = pyotp.TOTP(pending_secret)
    if not totp.verify(code):
        raise HTTPException(400, "Invalid code")

    # Activate MFA
    mfa_secrets_db[current_user.id] = pending_secret
    mfa_backup_codes_db[current_user.id] = mfa_backup_codes_db.pop(
        f"pending_{current_user.id}"
    )
    del mfa_secrets_db[f"pending_{current_user.id}"]

    return {"message": "MFA enabled"}


# Login with MFA
@app.post("/login")
async def login(credentials: LoginRequest):
    user = authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(401, "Invalid credentials")

    # Check if MFA is enabled
    if user.id in mfa_secrets_db:
        # Create pending MFA session
        session_token = secrets.token_urlsafe(32)
        pending_mfa_sessions[session_token] = {
            "user_id": user.id,
            "expires": datetime.utcnow() + timedelta(minutes=5)
        }
        return {"requires_mfa": True, "session_token": session_token}

    # No MFA, return tokens directly
    return create_tokens(user)


@app.post("/login/mfa")
async def verify_mfa(request: MFAVerifyRequest):
    session = pending_mfa_sessions.get(request.session_token)
    if not session:
        raise HTTPException(401, "Invalid session")

    if datetime.utcnow() > session["expires"]:
        del pending_mfa_sessions[request.session_token]
        raise HTTPException(401, "Session expired")

    user_id = session["user_id"]
    secret = mfa_secrets_db.get(user_id)

    # Try TOTP code
    totp = pyotp.TOTP(secret)
    if totp.verify(request.code, valid_window=1):
        del pending_mfa_sessions[request.session_token]
        user = get_user_by_id(user_id)
        return create_tokens(user)

    # Try backup code
    backup_codes = mfa_backup_codes_db.get(user_id, [])
    if request.code.upper() in backup_codes:
        backup_codes.remove(request.code.upper())
        mfa_backup_codes_db[user_id] = backup_codes
        del pending_mfa_sessions[request.session_token]
        user = get_user_by_id(user_id)
        return create_tokens(user)

    raise HTTPException(401, "Invalid MFA code")


# Disable MFA
@app.post("/mfa/disable")
async def disable_mfa(code: str, current_user: CurrentUser):
    secret = mfa_secrets_db.get(current_user.id)
    if not secret:
        raise HTTPException(400, "MFA not enabled")

    totp = pyotp.TOTP(secret)
    if not totp.verify(code):
        raise HTTPException(400, "Invalid code")

    del mfa_secrets_db[current_user.id]
    mfa_backup_codes_db.pop(current_user.id, None)

    return {"message": "MFA disabled"}
```

---

## 2.2 Authorization Patterns

### Role-Based Access Control (RBAC)

```python
from fastapi import FastAPI, Depends, HTTPException
from enum import Enum
from typing import Annotated
from functools import wraps

app = FastAPI()

class Role(str, Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

# Role hierarchy - higher roles inherit lower permissions
ROLE_HIERARCHY = {
    Role.VIEWER: [],
    Role.EDITOR: [Role.VIEWER],
    Role.ADMIN: [Role.VIEWER, Role.EDITOR],
    Role.SUPER_ADMIN: [Role.VIEWER, Role.EDITOR, Role.ADMIN]
}

def get_all_roles(role: Role) -> set[Role]:
    """Get all roles a user has access to (including inherited)"""
    roles = {role}
    for inherited in ROLE_HIERARCHY.get(role, []):
        roles.update(get_all_roles(inherited))
    return roles

class User(BaseModel):
    id: int
    username: str
    role: Role

def require_role(required_role: Role):
    """Dependency that checks if user has required role"""
    async def check_role(current_user: CurrentUser) -> User:
        user_roles = get_all_roles(current_user.role)
        if required_role not in user_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role {required_role.value} required"
            )
        return current_user
    return check_role

# Type aliases for common role checks
AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]
EditorUser = Annotated[User, Depends(require_role(Role.EDITOR))]
ViewerUser = Annotated[User, Depends(require_role(Role.VIEWER))]

@app.get("/reports")
async def view_reports(user: ViewerUser):
    return {"reports": [...]}

@app.post("/articles")
async def create_article(user: EditorUser, article: ArticleCreate):
    return {"message": "Article created"}

@app.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: AdminUser):
    return {"message": f"User {user_id} deleted"}


# Multiple roles allowed
def require_any_role(*roles: Role):
    async def check_role(current_user: CurrentUser) -> User:
        user_roles = get_all_roles(current_user.role)
        if not any(r in user_roles for r in roles):
            raise HTTPException(
                status_code=403,
                detail=f"One of {[r.value for r in roles]} required"
            )
        return current_user
    return check_role

@app.post("/moderate")
async def moderate_content(
    user: Annotated[User, Depends(require_any_role(Role.EDITOR, Role.ADMIN))]
):
    return {"message": "Content moderated"}
```

### Permission-Based Authorization

```python
from fastapi import FastAPI, Depends, HTTPException
from enum import Enum, auto
from typing import Annotated

app = FastAPI()

class Permission(str, Enum):
    # User permissions
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    # Article permissions
    ARTICLE_READ = "article:read"
    ARTICLE_CREATE = "article:create"
    ARTICLE_UPDATE = "article:update"
    ARTICLE_DELETE = "article:delete"
    ARTICLE_PUBLISH = "article:publish"

    # Admin permissions
    ADMIN_ACCESS = "admin:access"
    SETTINGS_MANAGE = "settings:manage"

# Permission sets for roles
ROLE_PERMISSIONS = {
    "viewer": {
        Permission.USER_READ,
        Permission.ARTICLE_READ
    },
    "author": {
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.ARTICLE_READ,
        Permission.ARTICLE_CREATE,
        Permission.ARTICLE_UPDATE
    },
    "editor": {
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.ARTICLE_READ,
        Permission.ARTICLE_CREATE,
        Permission.ARTICLE_UPDATE,
        Permission.ARTICLE_DELETE,
        Permission.ARTICLE_PUBLISH
    },
    "admin": set(Permission)  # All permissions
}

class User(BaseModel):
    id: int
    username: str
    role: str
    extra_permissions: list[Permission] = []
    denied_permissions: list[Permission] = []

def get_user_permissions(user: User) -> set[Permission]:
    """Get effective permissions for user"""
    permissions = ROLE_PERMISSIONS.get(user.role, set()).copy()
    permissions.update(user.extra_permissions)
    permissions -= set(user.denied_permissions)
    return permissions

def require_permission(*required: Permission):
    """Check if user has all required permissions"""
    async def check(current_user: CurrentUser) -> User:
        user_permissions = get_user_permissions(current_user)
        missing = set(required) - user_permissions
        if missing:
            raise HTTPException(
                status_code=403,
                detail=f"Missing permissions: {[p.value for p in missing]}"
            )
        return current_user
    return check

def require_any_permission(*required: Permission):
    """Check if user has any of the required permissions"""
    async def check(current_user: CurrentUser) -> User:
        user_permissions = get_user_permissions(current_user)
        if not any(p in user_permissions for p in required):
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions"
            )
        return current_user
    return check


# Usage
@app.get("/users")
async def list_users(
    user: Annotated[User, Depends(require_permission(Permission.USER_READ))]
):
    return {"users": [...]}

@app.post("/articles")
async def create_article(
    user: Annotated[User, Depends(require_permission(Permission.ARTICLE_CREATE))]
):
    return {"message": "Created"}

@app.post("/articles/{id}/publish")
async def publish_article(
    id: int,
    user: Annotated[User, Depends(require_permission(
        Permission.ARTICLE_UPDATE,
        Permission.ARTICLE_PUBLISH
    ))]
):
    return {"message": "Published"}


# Check permissions in code
@app.get("/dashboard")
async def dashboard(current_user: CurrentUser):
    permissions = get_user_permissions(current_user)

    data = {"user": current_user.username}

    if Permission.ADMIN_ACCESS in permissions:
        data["admin_stats"] = get_admin_stats()

    if Permission.ARTICLE_READ in permissions:
        data["articles"] = get_articles()

    return data
```

### Resource-Level Permissions

```python
from fastapi import FastAPI, Depends, HTTPException
from typing import Annotated
from enum import Enum

app = FastAPI()

class ResourceAction(str, Enum):
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    SHARE = "share"

class Document(BaseModel):
    id: int
    title: str
    owner_id: int
    is_public: bool = False

# Document permissions storage
# Structure: {document_id: {user_id: [actions]}}
document_permissions: dict[int, dict[int, list[ResourceAction]]] = {
    1: {
        10: [ResourceAction.READ, ResourceAction.UPDATE],
        20: [ResourceAction.READ]
    }
}

def get_document(document_id: int) -> Document:
    # Fetch from database
    return Document(id=document_id, title="Test", owner_id=1, is_public=False)

def check_document_permission(action: ResourceAction):
    """Check if user can perform action on document"""
    async def checker(
        document_id: int,
        current_user: CurrentUser
    ) -> Document:
        document = get_document(document_id)

        # Owner has all permissions
        if document.owner_id == current_user.id:
            return document

        # Public documents allow read
        if document.is_public and action == ResourceAction.READ:
            return document

        # Check explicit permissions
        doc_perms = document_permissions.get(document_id, {})
        user_perms = doc_perms.get(current_user.id, [])

        if action not in user_perms:
            raise HTTPException(
                status_code=403,
                detail=f"No {action.value} permission for this document"
            )

        return document

    return checker


@app.get("/documents/{document_id}")
async def get_document_endpoint(
    document: Annotated[
        Document,
        Depends(check_document_permission(ResourceAction.READ))
    ]
):
    return document

@app.put("/documents/{document_id}")
async def update_document(
    document: Annotated[
        Document,
        Depends(check_document_permission(ResourceAction.UPDATE))
    ],
    data: DocumentUpdate
):
    return {"message": "Updated", "document": document}

@app.delete("/documents/{document_id}")
async def delete_document(
    document: Annotated[
        Document,
        Depends(check_document_permission(ResourceAction.DELETE))
    ]
):
    return {"message": "Deleted"}


# Share document (grant permissions)
class ShareRequest(BaseModel):
    user_id: int
    permissions: list[ResourceAction]

@app.post("/documents/{document_id}/share")
async def share_document(
    document_id: int,
    share: ShareRequest,
    document: Annotated[
        Document,
        Depends(check_document_permission(ResourceAction.SHARE))
    ]
):
    if document_id not in document_permissions:
        document_permissions[document_id] = {}

    document_permissions[document_id][share.user_id] = share.permissions

    return {"message": f"Shared with user {share.user_id}"}
```

### Dependency-Based Authorization Guards

```python
from fastapi import FastAPI, Depends, HTTPException, Request
from typing import Annotated, Callable
from functools import wraps

app = FastAPI()

# Generic guard factory
def guard(
    condition: Callable[[User, Request], bool],
    error_message: str = "Access denied"
):
    async def check(current_user: CurrentUser, request: Request):
        if not condition(current_user, request):
            raise HTTPException(status_code=403, detail=error_message)
        return current_user
    return check

# Specific guards
is_verified = guard(
    lambda user, req: user.is_verified,
    "Email verification required"
)

is_premium = guard(
    lambda user, req: user.subscription == "premium",
    "Premium subscription required"
)

is_not_banned = guard(
    lambda user, req: not user.is_banned,
    "Account is banned"
)

owns_resource = lambda resource_param: guard(
    lambda user, req: int(req.path_params.get(resource_param, 0)) == user.id,
    "You can only access your own resources"
)

# Combine guards
def all_guards(*guards):
    async def combined(current_user: CurrentUser, request: Request):
        for g in guards:
            await g(current_user, request)
        return current_user
    return combined

def any_guard(*guards):
    async def combined(current_user: CurrentUser, request: Request):
        errors = []
        for g in guards:
            try:
                await g(current_user, request)
                return current_user
            except HTTPException as e:
                errors.append(e.detail)
        raise HTTPException(403, f"Access denied: {errors}")
    return combined


# Usage
VerifiedUser = Annotated[User, Depends(is_verified)]
PremiumUser = Annotated[User, Depends(all_guards(is_verified, is_premium))]

@app.post("/premium-feature")
async def premium_feature(user: PremiumUser):
    return {"message": "Premium content"}

@app.get("/users/{user_id}/private")
async def user_private_data(
    user_id: int,
    user: Annotated[User, Depends(owns_resource("user_id"))]
):
    return {"private": "data"}


# Rate limit guard
from datetime import datetime

request_counts: dict[int, list[datetime]] = {}

def rate_limit(max_requests: int, window_seconds: int):
    async def check(current_user: CurrentUser, request: Request):
        now = datetime.utcnow()
        user_requests = request_counts.get(current_user.id, [])

        # Remove old requests
        cutoff = now - timedelta(seconds=window_seconds)
        user_requests = [r for r in user_requests if r > cutoff]

        if len(user_requests) >= max_requests:
            raise HTTPException(429, "Rate limit exceeded")

        user_requests.append(now)
        request_counts[current_user.id] = user_requests
        return current_user

    return check

@app.post("/expensive-operation")
async def expensive_operation(
    user: Annotated[User, Depends(rate_limit(10, 60))]  # 10 per minute
):
    return {"result": "done"}
```

### Custom Security Schemes

```python
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security.base import SecurityBase
from fastapi.security import SecurityScopes
from fastapi.openapi.models import SecurityScheme as SecuritySchemeModel
from typing import Annotated

app = FastAPI()

# Custom security scheme for signed requests
class SignedRequestAuth(SecurityBase):
    def __init__(
        self,
        *,
        scheme_name: str = "SignedRequest",
        description: str = "Request signed with HMAC"
    ):
        self.model = SecuritySchemeModel(
            type="apiKey",
            in_="header",
            name="X-Signature",
            description=description
        )
        self.scheme_name = scheme_name

    async def __call__(self, request: Request) -> dict:
        signature = request.headers.get("X-Signature")
        timestamp = request.headers.get("X-Timestamp")
        api_key = request.headers.get("X-API-Key")

        if not all([signature, timestamp, api_key]):
            raise HTTPException(
                status_code=401,
                detail="Missing authentication headers"
            )

        # Verify signature
        if not self._verify_signature(request, signature, timestamp, api_key):
            raise HTTPException(
                status_code=401,
                detail="Invalid signature"
            )

        return {"api_key": api_key, "timestamp": timestamp}

    def _verify_signature(
        self,
        request: Request,
        signature: str,
        timestamp: str,
        api_key: str
    ) -> bool:
        import hmac
        import hashlib

        # Get secret for API key
        secret = get_api_key_secret(api_key)
        if not secret:
            return False

        # Build string to sign
        body = request._body.decode() if hasattr(request, '_body') else ""
        string_to_sign = f"{request.method}\n{request.url.path}\n{timestamp}\n{body}"

        # Calculate expected signature
        expected = hmac.new(
            secret.encode(),
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected)


signed_auth = SignedRequestAuth()

@app.post("/secure-webhook")
async def handle_webhook(
    auth: Annotated[dict, Depends(signed_auth)],
    payload: dict
):
    return {"received": True, "api_key": auth["api_key"]}


# Custom JWT with additional claims
class EnhancedJWTAuth(SecurityBase):
    def __init__(self):
        self.model = SecuritySchemeModel(
            type="http",
            scheme="bearer",
            bearerFormat="JWT"
        )
        self.scheme_name = "EnhancedJWT"

    async def __call__(
        self,
        request: Request,
        security_scopes: SecurityScopes
    ) -> dict:
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            raise HTTPException(401, "Missing token")

        token = auth.replace("Bearer ", "")

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Invalid token")

        # Custom claim validation
        if payload.get("token_type") != "access":
            raise HTTPException(401, "Invalid token type")

        # IP binding
        if payload.get("bound_ip"):
            client_ip = request.client.host
            if payload["bound_ip"] != client_ip:
                raise HTTPException(401, "Token not valid for this IP")

        # Device binding
        device_id = request.headers.get("X-Device-ID")
        if payload.get("device_id") and payload["device_id"] != device_id:
            raise HTTPException(401, "Token not valid for this device")

        return payload

enhanced_jwt = EnhancedJWTAuth()

@app.get("/secure")
async def secure_endpoint(
    claims: Annotated[dict, Depends(enhanced_jwt)]
):
    return {"user_id": claims["sub"]}
```

---

## 2.3 Security Hardening

### CORS Configuration

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Development - permissive
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Production - restrictive
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://myapp.com",
        "https://www.myapp.com",
        "https://admin.myapp.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-API-Key"
    ],
    expose_headers=[
        "X-Request-ID",
        "X-RateLimit-Remaining"
    ],
    max_age=3600  # Preflight cache duration
)


# Dynamic CORS based on environment
import os

def get_cors_origins() -> list[str]:
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        return ["https://myapp.com", "https://www.myapp.com"]
    elif env == "staging":
        return ["https://staging.myapp.com"]
    else:
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Per-route CORS (using custom middleware)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class CustomCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        origin = request.headers.get("origin")
        if not origin:
            return response

        # Different rules for different paths
        if request.url.path.startswith("/api/public"):
            # Allow any origin for public endpoints
            response.headers["Access-Control-Allow-Origin"] = origin
        elif request.url.path.startswith("/api/internal"):
            # Only allow internal origins
            if origin in ["https://internal.myapp.com"]:
                response.headers["Access-Control-Allow-Origin"] = origin
        else:
            # Default CORS
            if origin in get_cors_origins():
                response.headers["Access-Control-Allow-Origin"] = origin

        return response

app.add_middleware(CustomCORSMiddleware)
```

### CSRF Protection

```python
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
import secrets
import hmac
import hashlib
from datetime import datetime, timedelta

app = FastAPI()

CSRF_SECRET = "your-csrf-secret-key"
CSRF_TOKEN_EXPIRY = timedelta(hours=24)

def generate_csrf_token(session_id: str) -> str:
    """Generate CSRF token tied to session"""
    timestamp = str(int(datetime.utcnow().timestamp()))
    message = f"{session_id}:{timestamp}"
    signature = hmac.new(
        CSRF_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{timestamp}:{signature}"

def validate_csrf_token(session_id: str, token: str) -> bool:
    """Validate CSRF token"""
    try:
        timestamp, signature = token.split(":")
        token_time = datetime.fromtimestamp(int(timestamp))

        # Check expiry
        if datetime.utcnow() - token_time > CSRF_TOKEN_EXPIRY:
            return False

        # Verify signature
        message = f"{session_id}:{timestamp}"
        expected = hmac.new(
            CSRF_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected)
    except:
        return False


# CSRF middleware
from starlette.middleware.base import BaseHTTPMiddleware

class CSRFMiddleware(BaseHTTPMiddleware):
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
    CSRF_HEADER = "X-CSRF-Token"
    CSRF_COOKIE = "csrf_token"

    async def dispatch(self, request: Request, call_next):
        # Skip CSRF for safe methods
        if request.method in self.SAFE_METHODS:
            response = await call_next(request)
            # Set CSRF cookie for GET requests
            session_id = request.cookies.get("session_id", "anonymous")
            csrf_token = generate_csrf_token(session_id)
            response.set_cookie(
                self.CSRF_COOKIE,
                csrf_token,
                httponly=False,  # JS needs to read this
                secure=True,
                samesite="strict"
            )
            return response

        # Validate CSRF token for unsafe methods
        session_id = request.cookies.get("session_id", "anonymous")
        csrf_token = request.headers.get(self.CSRF_HEADER)

        if not csrf_token:
            return JSONResponse(
                {"detail": "CSRF token missing"},
                status_code=403
            )

        if not validate_csrf_token(session_id, csrf_token):
            return JSONResponse(
                {"detail": "Invalid CSRF token"},
                status_code=403
            )

        return await call_next(request)

app.add_middleware(CSRFMiddleware)


# Double-submit cookie pattern
class DoubleSubmitCSRF:
    def __init__(self):
        self.cookie_name = "csrf_token"
        self.header_name = "X-CSRF-Token"

    async def __call__(self, request: Request):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return

        cookie_token = request.cookies.get(self.cookie_name)
        header_token = request.headers.get(self.header_name)

        if not cookie_token or not header_token:
            raise HTTPException(403, "CSRF token missing")

        if not secrets.compare_digest(cookie_token, header_token):
            raise HTTPException(403, "CSRF token mismatch")

csrf_protect = DoubleSubmitCSRF()

@app.post("/transfer")
async def transfer_funds(
    _: None = Depends(csrf_protect),
    data: TransferRequest = ...
):
    return {"message": "Transfer complete"}
```

### Input Sanitization

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator, Field
import re
import html
import bleach

app = FastAPI()

# HTML sanitization with bleach
ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'a', 'ul', 'ol', 'li']
ALLOWED_ATTRIBUTES = {'a': ['href', 'title']}

def sanitize_html(content: str) -> str:
    """Remove dangerous HTML, keep safe tags"""
    return bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )

def escape_html(content: str) -> str:
    """Escape all HTML entities"""
    return html.escape(content)

def strip_html(content: str) -> str:
    """Remove all HTML tags"""
    return bleach.clean(content, tags=[], strip=True)


class CommentCreate(BaseModel):
    content: str = Field(max_length=5000)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        return sanitize_html(v)


class UserProfile(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    bio: str = Field(max_length=500)
    website: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        # Only alphanumeric and underscores
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError("Username can only contain letters, numbers, and underscores")
        # No consecutive underscores
        if '__' in v:
            raise ValueError("Username cannot have consecutive underscores")
        # Reserved usernames
        reserved = ['admin', 'root', 'system', 'moderator']
        if v.lower() in reserved:
            raise ValueError("This username is reserved")
        return v.lower()

    @field_validator("bio")
    @classmethod
    def sanitize_bio(cls, v: str) -> str:
        return strip_html(v)

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Only allow http/https URLs
        if not re.match(r'^https?://', v):
            raise ValueError("Website must start with http:// or https://")
        # Block certain domains
        blocked = ['malware.com', 'phishing.net']
        for domain in blocked:
            if domain in v:
                raise ValueError("This website is not allowed")
        return v


# SQL injection prevention (parameterized queries)
from sqlalchemy import text

@app.get("/search")
async def search_items(q: str, db: DB):
    # WRONG - vulnerable to SQL injection
    # result = await db.execute(f"SELECT * FROM items WHERE name LIKE '%{q}%'")

    # CORRECT - parameterized query
    result = await db.execute(
        text("SELECT * FROM items WHERE name LIKE :search"),
        {"search": f"%{q}%"}
    )
    return result.all()


# Path traversal prevention
import os

UPLOAD_DIR = "/var/uploads"

def safe_path_join(base: str, filename: str) -> str:
    """Safely join paths, preventing directory traversal"""
    # Remove any path separators from filename
    safe_name = os.path.basename(filename)
    # Resolve the full path
    full_path = os.path.realpath(os.path.join(base, safe_name))
    # Ensure it's still within the base directory
    if not full_path.startswith(os.path.realpath(base)):
        raise ValueError("Invalid path")
    return full_path

@app.get("/files/{filename}")
async def get_file(filename: str):
    try:
        path = safe_path_join(UPLOAD_DIR, filename)
    except ValueError:
        raise HTTPException(400, "Invalid filename")
    return FileResponse(path)
```

### Rate Limiting Implementation

```python
from fastapi import FastAPI, Depends, HTTPException, Request
from typing import Annotated
from datetime import datetime, timedelta
import asyncio
import redis.asyncio as redis

app = FastAPI()

# In-memory rate limiter (for single instance)
class InMemoryRateLimiter:
    def __init__(self):
        self.requests: dict[str, list[datetime]] = {}
        self.lock = asyncio.Lock()

    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> tuple[bool, int]:
        async with self.lock:
            now = datetime.utcnow()
            cutoff = now - timedelta(seconds=window_seconds)

            # Get and clean request timestamps
            timestamps = self.requests.get(key, [])
            timestamps = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= max_requests:
                retry_after = int((timestamps[0] - cutoff).total_seconds()) + 1
                return False, retry_after

            timestamps.append(now)
            self.requests[key] = timestamps

            return True, 0

rate_limiter = InMemoryRateLimiter()


# Redis rate limiter (for distributed systems)
class RedisRateLimiter:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> tuple[bool, int]:
        now = datetime.utcnow().timestamp()
        window_start = now - window_seconds

        pipe = self.redis.pipeline()
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        # Count current entries
        pipe.zcard(key)
        # Add current request
        pipe.zadd(key, {str(now): now})
        # Set expiry
        pipe.expire(key, window_seconds)

        results = await pipe.execute()
        current_count = results[1]

        if current_count >= max_requests:
            # Get oldest entry to calculate retry-after
            oldest = await self.redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(oldest[0][1] + window_seconds - now) + 1
                return False, max(retry_after, 1)
            return False, 1

        return True, 0


# Sliding window rate limit dependency
def rate_limit(
    max_requests: int = 100,
    window_seconds: int = 60,
    key_func: callable = None
):
    async def dependency(request: Request):
        # Determine rate limit key
        if key_func:
            key = key_func(request)
        else:
            # Default: IP-based
            key = f"rate_limit:{request.client.host}"

        allowed, retry_after = await rate_limiter.is_allowed(
            key, max_requests, window_seconds
        )

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)}
            )

    return dependency


# User-based rate limit
def user_key(request: Request) -> str:
    user_id = request.state.user_id if hasattr(request.state, 'user_id') else "anonymous"
    return f"rate_limit:user:{user_id}"


@app.get("/api/data")
async def get_data(
    _: None = Depends(rate_limit(max_requests=100, window_seconds=60))
):
    return {"data": "..."}

@app.post("/api/expensive")
async def expensive_operation(
    _: None = Depends(rate_limit(
        max_requests=10,
        window_seconds=3600,
        key_func=user_key
    ))
):
    return {"result": "..."}


# Rate limit with response headers
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, default_limit: int = 100, window: int = 60):
        super().__init__(app)
        self.default_limit = default_limit
        self.window = window
        self.limiter = InMemoryRateLimiter()

    async def dispatch(self, request: Request, call_next):
        key = f"rate:{request.client.host}"

        allowed, retry_after = await self.limiter.is_allowed(
            key, self.default_limit, self.window
        )

        if not allowed:
            return JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.default_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(datetime.utcnow().timestamp()) + retry_after)
                }
            )

        response = await call_next(request)

        # Add rate limit headers
        timestamps = self.limiter.requests.get(key, [])
        remaining = max(0, self.default_limit - len(timestamps))

        response.headers["X-RateLimit-Limit"] = str(self.default_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(
            int(datetime.utcnow().timestamp()) + self.window
        )

        return response

app.add_middleware(RateLimitMiddleware, default_limit=100, window=60)
```

### Security Headers Middleware

```python
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

app = FastAPI()

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy
        response.headers["Content-Security-Policy"] = "; ".join([
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline'",  # Adjust as needed
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self'",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "base-uri 'self'"
        ])

        # Permissions Policy (formerly Feature-Policy)
        response.headers["Permissions-Policy"] = ", ".join([
            "accelerometer=()",
            "camera=()",
            "geolocation=()",
            "gyroscope=()",
            "magnetometer=()",
            "microphone=()",
            "payment=()",
            "usb=()"
        ])

        # Strict Transport Security (HTTPS only)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # Cache control for sensitive pages
        if "/api/" in request.url.path:
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, private"
            )
            response.headers["Pragma"] = "no-cache"

        return response

app.add_middleware(SecurityHeadersMiddleware)


# Environment-specific CSP
import os

def get_csp_policy() -> str:
    env = os.getenv("ENVIRONMENT", "development")

    if env == "development":
        # Relaxed CSP for development
        return "; ".join([
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
            "style-src 'self' 'unsafe-inline'",
            "connect-src 'self' ws://localhost:*"
        ])
    else:
        # Strict CSP for production
        return "; ".join([
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            "img-src 'self' https://cdn.example.com",
            "connect-src 'self' https://api.example.com",
            "frame-ancestors 'none'",
            "upgrade-insecure-requests"
        ])
```

### Secrets Management

```python
from pydantic_settings import BaseSettings
from pydantic import SecretStr, Field
import os

# Using pydantic-settings for secure configuration
class Settings(BaseSettings):
    # Database
    database_url: SecretStr
    database_password: SecretStr

    # JWT
    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"

    # API Keys
    api_key_salt: SecretStr
    external_api_key: SecretStr | None = None

    # OAuth
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None

    # Encryption
    encryption_key: SecretStr

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }

settings = Settings()

# Accessing secrets
# settings.jwt_secret_key.get_secret_value()


# AWS Secrets Manager integration
import boto3
from functools import lru_cache

@lru_cache()
def get_secret(secret_name: str) -> dict:
    """Fetch secret from AWS Secrets Manager"""
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


class AWSSettings(BaseSettings):
    """Settings that fetch from AWS Secrets Manager"""
    aws_region: str = "us-east-1"
    secret_name: str = "myapp/production"

    @property
    def database_url(self) -> str:
        secrets = get_secret(self.secret_name)
        return secrets["database_url"]

    @property
    def jwt_secret(self) -> str:
        secrets = get_secret(self.secret_name)
        return secrets["jwt_secret"]


# HashiCorp Vault integration
import hvac

class VaultClient:
    def __init__(self, url: str, token: str):
        self.client = hvac.Client(url=url, token=token)

    def get_secret(self, path: str) -> dict:
        result = self.client.secrets.kv.v2.read_secret_version(path=path)
        return result["data"]["data"]

vault = VaultClient(
    url=os.getenv("VAULT_URL"),
    token=os.getenv("VAULT_TOKEN")
)


# Encrypted environment variables
from cryptography.fernet import Fernet

def decrypt_env(key: bytes, encrypted_value: str) -> str:
    """Decrypt environment variable value"""
    f = Fernet(key)
    return f.decrypt(encrypted_value.encode()).decode()

# Usage:
# ENCRYPTION_KEY in env (never committed)
# DATABASE_PASSWORD encrypted value in env
encryption_key = os.getenv("ENCRYPTION_KEY").encode()
db_password = decrypt_env(
    encryption_key,
    os.getenv("DATABASE_PASSWORD_ENCRYPTED")
)
```

### HTTPS Enforcement

```python
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
import os

app = FastAPI()

# HTTPS redirect middleware
class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check if behind a proxy
        forwarded_proto = request.headers.get("X-Forwarded-Proto")

        if forwarded_proto == "http":
            # Redirect to HTTPS
            url = request.url.replace(scheme="https")
            return RedirectResponse(url, status_code=301)

        # Direct connection check
        if request.url.scheme == "http" and os.getenv("ENVIRONMENT") == "production":
            url = request.url.replace(scheme="https")
            return RedirectResponse(url, status_code=301)

        return await call_next(request)

app.add_middleware(HTTPSRedirectMiddleware)


# Trust proxy headers
class TrustedProxyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, trusted_proxies: list[str]):
        super().__init__(app)
        self.trusted_proxies = set(trusted_proxies)

    async def dispatch(self, request: Request, call_next):
        # Only trust headers from known proxies
        client_ip = request.client.host

        if client_ip in self.trusted_proxies:
            # Use X-Forwarded-For for real client IP
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                # Take the first IP (original client)
                real_ip = forwarded_for.split(",")[0].strip()
                # Modify request state
                request.state.real_ip = real_ip

        return await call_next(request)

app.add_middleware(
    TrustedProxyMiddleware,
    trusted_proxies=["10.0.0.1", "10.0.0.2"]  # Load balancer IPs
)


# Enforce HTTPS in OpenAPI
app = FastAPI(
    servers=[
        {"url": "https://api.example.com", "description": "Production"},
        {"url": "https://staging-api.example.com", "description": "Staging"}
    ]
)

# Production Uvicorn with SSL
# uvicorn main:app --host 0.0.0.0 --port 443 --ssl-keyfile key.pem --ssl-certfile cert.pem
```

---

## Summary

Module 2 covered comprehensive authentication and security topics:

1. **Authentication Mechanisms** - OAuth2 password flow, JWT tokens, refresh token rotation, OAuth2 scopes, API keys, HTTP Basic auth, and MFA patterns

2. **Authorization Patterns** - RBAC, permission-based auth, resource-level permissions, dependency-based guards, and custom security schemes

3. **Security Hardening** - CORS configuration, CSRF protection, input sanitization, rate limiting, security headers, secrets management, and HTTPS enforcement

These security practices are essential for building production-ready FastAPI applications and protecting against common web vulnerabilities.
