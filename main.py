"""
Phần 1: Luồng dữ liệu (Data Flow)
Client gửi POST /memberships
  { "card_number": "VIP001", "customer_id": 5 }
        │
        ▼
[BƯỚC 1] SELECT xác thực customer_id có tồn tại không
  db.query(CustomerModel).filter(CustomerModel.id == customer_id).first()
        │
        ├── customer là None (không tồn tại)
        │        │
        │        ▼
        │   raise HTTPException(404, "Khách hàng không tồn tại trên hệ thống")
        │   → dừng ngay, KHÔNG chạy tới bước INSERT
        │
        └── customer tồn tại → tiếp tục BƯỚC 2

[BƯỚC 2] SELECT kiểm tra card_number đã bị trùng chưa
  db.query(MembershipModel).filter(MembershipModel.card_number == card_number).first()
        │
        ├── tồn tại bản ghi trùng
        │        │
        │        ▼
        │   raise HTTPException(400, "Mã số thẻ thành viên này đã được sử dụng")
        │   → dừng ngay, KHÔNG chạy tới bước INSERT
        │
        └── không trùng → tiếp tục BƯỚC 3

[BƯỚC 3] Cả 2 điều kiện xác thực đều PASS
  → db.add(new_membership)
  → db.commit()
  → db.refresh(new_membership)
  → trả về 201 Created + dữ liệu bản ghi vừa tạo
Quy tắc quyết định:

db.add() chỉ được gọi khi cả 2 lệnh SELECT xác thực đều trả về kết quả mong muốn (customer tồn tại VÀ card_number chưa bị trùng).
Bất kỳ điều kiện xác thực nào thất bại → raise HTTPException ngay lập tức, cắt luồng xử lý, không chạm tới DB ghi dữ liệu (transaction an toàn, tránh vi phạm khóa ngoại ở tầng MySQL).
Toàn bộ response (thành công lẫn thất bại) đều tuân theo cấu trúc 6 trường cố định để Frontend xử lý đồng nhất, không cần if/else theo từng loại lỗi.

Cấu trúc chuẩn 6 trường:
TrườngKiểuÝ nghĩastatusstr"success" hoặc "error"status_codeintMã HTTP tương ứng (201, 404, 400, 500)messagestrThông điệp mô tả kết quảdataobject | nullDữ liệu bản ghi (chỉ có khi thành công)errorstr | nullLoại lỗi kỹ thuật (chỉ có khi thất bại)timestampstrThời điểm xử lý request (ISO format)
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone

from database import get_db
from models import CustomerModel, MembershipModel
from schemas import MembershipCreateRequest

app = FastAPI()


def build_response(status: str, status_code: int, message: str,
                    data=None, error: str = None):
    """Đóng gói phản hồi đồng bộ 6 trường cho cả thành công và thất bại."""
    return {
        "status": status,
        "status_code": status_code,
        "message": message,
        "data": data,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/memberships", status_code=201)
def create_membership(payload: MembershipCreateRequest, db: Session = Depends(get_db)):
    try:
        # BƯỚC 1: SELECT xác thực customer_id có tồn tại trong bảng customers không
        # -> Ngăn lỗi ForeignKeyViolationError từ MySQL trước khi INSERT
        customer = db.query(CustomerModel).filter(
            CustomerModel.id == payload.customer_id
        ).first()

        if customer is None:
            raise HTTPException(
                status_code=404,
                detail="Khách hàng không tồn tại trên hệ thống"
            )

        # BƯỚC 2: SELECT kiểm tra card_number đã tồn tại (tránh vi phạm unique constraint)
        existing_card = db.query(MembershipModel).filter(
            MembershipModel.card_number == payload.card_number
        ).first()

        if existing_card is not None:
            raise HTTPException(
                status_code=400,
                detail="Mã số thẻ thành viên này đã được sử dụng"
            )

        # BƯỚC 3: Cả 2 xác thực đều PASS -> tiến hành INSERT an toàn
        new_membership = MembershipModel(
            card_number=payload.card_number,
            customer_id=payload.customer_id
        )
        db.add(new_membership)
        db.commit()
        db.refresh(new_membership)

        return JSONResponse(
            status_code=201,
            content=build_response(
                status="success",
                status_code=201,
                message="Tạo thẻ thành viên VIP thành công",
                data={
                    "id": new_membership.id,
                    "card_number": new_membership.card_number,
                    "customer_id": new_membership.customer_id
                }
            )
        )

    except HTTPException as http_err:
        # Bắt và ném lại HTTPException TRƯỚC generic Exception
        # (tránh bug quen thuộc: except Exception nuốt mất lỗi 404/400)
        db.rollback()
        return JSONResponse(
            status_code=http_err.status_code,
            content=build_response(
                status="error",
                status_code=http_err.status_code,
                message=http_err.detail,
                error="BusinessRuleViolation"
            )
        )

    except SQLAlchemyError:
        # Lỗi DB không lường trước (mất kết nối, timeout...) -> không lộ stack trace thô
        db.rollback()
        return JSONResponse(
            status_code=500,
            content=build_response(
                status="error",
                status_code=500,
                message="Lỗi hệ thống khi xử lý dữ liệu",
                error="DatabaseError"
            )
        )

    finally:
        pass
