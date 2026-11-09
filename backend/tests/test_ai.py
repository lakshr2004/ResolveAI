from unittest.mock import patch
from app.services.ai_service import analyze_and_resolve
from app.schemas import Classification
from app.services.llm_service import generate_resolution
from app.models import Ticket
import pytest

def test_llm_failure_preserves_ticket_and_escalates(client):
    from app.database import SessionLocal
    response=client.post('/api/tickets',json={'customer_name':'Asha Sharma','customer_email':'asha@example.com',
      'subject':'Payment failed unexpectedly','description':'My payment failed twice and the amount is not clear.'})
    tid=response.json()['ticket_id']
    with SessionLocal() as db:
        ticket=db.query(Ticket).filter_by(ticket_id=tid).first()
        with patch('app.services.ai_service.classify_ticket',side_effect=RuntimeError('offline')):
            result=analyze_and_resolve(db,ticket)
        assert result.available is False
        assert result.escalation_required is True
        assert db.query(Ticket).filter_by(ticket_id=tid).first() is not None
        assert db.query(Ticket).filter_by(ticket_id=tid).first().status=='Escalated'

def test_classification_schema_rejects_invalid_priority():
    with pytest.raises(Exception):
        Classification.model_validate({'category':'Billing & Payments','priority':'Urgent','sentiment':'Negative',
          'intent':'refund','main_issue':'charge','summary':'charge issue','recommended_next_action':'review'})

def test_resolution_rejects_fabricated_citation():
    ticket=Ticket(ticket_id='RAI-TEST',customer_name='Asha',customer_email='a@b.com',subject='Payment issue',description='Payment failed')
    classification=Classification(category='Billing & Payments',priority='High',sentiment='Negative',intent='payment failure',
      main_issue='Payment failed',summary='Payment failed',recommended_next_action='Review payment')
    evidence=[{'document_name':'billing.md','chunk_id':'chunk_0001','text':'Verify provider transaction status.'}]
    output={'summary':'Payment failed','category':'Billing & Payments','priority':'High','sentiment':'Negative',
      'root_cause':'Unknown','resolution_steps':['Check provider status'],'customer_response':'We are reviewing the payment.',
      'sources':[{'document_name':'invented.pdf','chunk_id':'chunk_9999'}],'confidence':0.5,
      'escalation_required':False,'escalation_reason':None}
    with patch('app.services.llm_service._complete',return_value=output):
        with pytest.raises(ValueError,match='citation'):
            generate_resolution(ticket,classification,evidence)
