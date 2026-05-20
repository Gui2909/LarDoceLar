import re

def patch():
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Imports
    content = content.replace("from datetime import date, datetime", "from datetime import date, datetime, timedelta")
    content = content.replace("from models.estoque import Estoque\n", "")
    
    # 2. Schemas
    content = content.replace("class CheckoutRequest(BaseModel):", "class OrderCreate(BaseModel):\n    customer_name: str\n\nclass CheckoutRequest(BaseModel):")
    
    content = content.replace(
        "class CashCloseRequest(BaseModel):\n    closing_amount: float = Field(ge=0)",
        "class CashCloseRequest(BaseModel):\n    closing_amount: float = Field(ge=0)\n    password: str | None = None\n\nclass PayInvoiceRequest(BaseModel):\n    payment_method: str"
    )
    
    # 3. Create Order
    old_create_order = """@app.post("/orders")
def create_order(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin", "cashier"})
    new_order = Order(status="ABERTO", total=0)
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order"""
    new_create_order = """@app.post("/orders")
def create_order(data: OrderCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin", "cashier"})
    session = get_open_cash_session(db)
    session_id = session.id if session else None
    new_order = Order(status="ABERTO", total=0, customer_name=data.customer_name, cash_session_id=session_id)
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order"""
    content = content.replace(old_create_order, new_create_order)

    # 4. Get Order (add customer_name to response)
    content = content.replace('"id": current.id,\n        "status": current.status', '"id": current.id,\n        "customer_name": current.customer_name,\n        "status": current.status')

    # 5. List Orders (filter by session)
    old_list_orders = """@app.get("/orders")
def list_orders(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status.upper())
    return query.order_by(Order.id.desc()).all()"""
    new_list_orders = """@app.get("/orders")
def list_orders(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles(current_user, {"admin", "cashier"})
    session = get_open_cash_session(db)
    if not session:
        return []
    query = db.query(Order).filter(Order.cash_session_id == session.id)
    if status:
        query = query.filter(Order.status == status.upper())
    return query.order_by(Order.id.desc()).all()"""
    content = content.replace(old_list_orders, new_list_orders)
    
    # 6. Checkout
    old_checkout = """    current_order.status = "FECHADO"
    db.add(
        CashFlow(
            order_id=current_order.id,
            cash_session_id=session.id,
            type="ENTRADA",
            amount=total,
            description=f"Venda pedido {current_order.id} (sessao {session.id})",
            payment_method=data.payment_method.upper(),
        )
    )
    db.commit()"""
    new_checkout = """    current_order.status = "FECHADO"
    current_order.payment_method = data.payment_method.upper()

    if current_order.payment_method == "FATURADO":
        current_order.payment_status = "PENDENTE"
    else:
        current_order.payment_status = "PAGO"
        db.add(
            CashFlow(
                order_id=current_order.id,
                cash_session_id=session.id,
                type="ENTRADA",
                amount=total,
                description=f"Venda pedido {current_order.id} (sessao {session.id})",
                payment_method=current_order.payment_method,
            )
        )
        
    db.commit()"""
    content = content.replace(old_checkout, new_checkout)

    # 7. Cash close
    old_close = """    current_open = get_open_cash_session(db)
    if current_open is None:
        raise HTTPException(status_code=400, detail="Nao ha caixa aberto")

    expected_amount = sum("""
    new_close = """    current_open = get_open_cash_session(db)
    if current_open is None:
        raise HTTPException(status_code=400, detail="Nao ha caixa aberto")

    open_orders = db.query(Order).filter(Order.status == "ABERTO", Order.cash_session_id == current_open.id).all()
    for o in open_orders:
        o.status = "FECHADO"
        o.payment_method = "FATURADO"
        o.payment_status = "PENDENTE"

    expected_amount = sum("""
    content = content.replace(old_close, new_close)

    # 8. Remove stock routes
    # From @app.post("/stock/{product_id}/in") to before @app.get("/")
    stock_start = content.find('@app.post("/stock/{product_id}/in")')
    stock_end = content.find('@app.get("/")', stock_start)
    if stock_start != -1 and stock_end != -1:
        content = content[:stock_start] + content[stock_end:]

    # 9. Add Invoices endpoints before @app.get("/")
    invoices_endpoints = """@app.get("/invoices")
def list_invoices(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_roles(current_user, {"admin", "cashier"})
    pending_orders = db.query(Order).filter(
        Order.payment_status == "PENDENTE", 
        Order.payment_method == "FATURADO"
    ).all()
    
    invoices = {}
    for o in pending_orders:
        if not o.customer_name:
            continue
        if o.customer_name not in invoices:
            invoices[o.customer_name] = {
                "customer_name": o.customer_name,
                "first_purchase": o.created_at,
                "total": 0.0,
                "orders": []
            }
        else:
            if o.created_at < invoices[o.customer_name]["first_purchase"]:
                invoices[o.customer_name]["first_purchase"] = o.created_at
        
        invoices[o.customer_name]["total"] += o.total
        invoices[o.customer_name]["orders"].append(o.id)
        
    result = []
    for customer, data in invoices.items():
        data["due_date"] = data["first_purchase"] + timedelta(days=30)
        result.append(data)
        
    return result

@app.post("/invoices/{customer_name}/pay")
def pay_invoice(
    customer_name: str,
    data: PayInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_roles(current_user, {"admin", "cashier"})
    session = get_open_cash_session(db)
    if session is None:
        raise HTTPException(status_code=400, detail="Caixa fechado. Abra o caixa antes de quitar dívidas.")
        
    pending_orders = db.query(Order).filter(
        Order.payment_status == "PENDENTE",
        Order.payment_method == "FATURADO",
        Order.customer_name == customer_name
    ).all()
    
    if not pending_orders:
        raise HTTPException(status_code=404, detail="Nenhuma dívida encontrada para este cliente.")
        
    total_paid = sum(o.total for o in pending_orders)
    
    for o in pending_orders:
        o.payment_status = "PAGO"
        
    db.add(
        CashFlow(
            cash_session_id=session.id,
            type="ENTRADA",
            amount=total_paid,
            description=f"Quitação faturado: {customer_name}",
            payment_method=data.payment_method.upper(),
        )
    )
    
    db.commit()
    return {"message": "Dívida quitada com sucesso", "total": total_paid}

"""
    content = content.replace('@app.get("/")', invoices_endpoints + '@app.get("/")')
    
    # 10. Serve frontend fix
    content = content.replace('@app.get("/")\ndef serve_frontend():\n    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))', '@app.get("/")\ndef index():\n    return FileResponse("frontend/index.html")')

    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Patch applied")

if __name__ == "__main__":
    patch()
