"""Fill a LOCAL database with clearly labelled sample data for walkthroughs.

    python -m app.demo_seed

Refuses to run unless ENVIRONMENT=local. Every sample record is marked
"(sample)" or uses example.com addresses, so it can never be mistaken for real
Eranova facts. Records go through the normal services (validation + audit).
"""

import asyncio
import secrets
import sys
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.cli import bootstrap, register_initial_products
from app.core.config import get_settings
from app.core.request_meta import SYSTEM_META
from app.db.session import dispose_engine, get_sessionmaker
from app.modules.authorization.models import Role, UserRole
from app.modules.authorization.service import grant_super_admin, load_principal
from app.modules.company.service import ensure_company
from app.modules.crm import service as crm
from app.modules.crm.customers import (
    ActivityIn,
    CustomerIn,
    SubscriptionIn,
    create_customer,
    upsert_subscription,
)
from app.modules.crm.schemas import LeadConvert, LeadCreate, LeadUpdate
from app.modules.documents import service as documents
from app.modules.identity.dev_login import DEV_EMAIL
from app.modules.identity.models import User
from app.modules.identity.service import create_user
from app.modules.integrations import service as integrations
from app.modules.marketing import service as marketing
from app.modules.products.models import Product, ProductStatusHistory
from app.modules.support import service as support
from app.modules.work import service as work
from app.modules.work.schemas import MilestoneIn, ProjectIn, TaskIn

MARKER_SLUG = "sample-app"
STAFF = [
    ("Sample Sales Rep", "sales.sample@example.com", "sales"),
    ("Sample Developer", "dev.sample@example.com", "developer"),
    ("Sample Support Agent", "support.sample@example.com", "support"),
    ("Sample Marketer", "marketing.sample@example.com", "marketing"),
]


async def _admin(session, company) -> User:
    user = await session.scalar(
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(User.company_id == company.id, Role.slug == "super_admin")
        .order_by(User.created_at)
        .limit(1)
    )
    if user:
        return user
    user = await session.scalar(select(User).where(User.email == DEV_EMAIL))
    if user is None:
        user = await create_user(
            session,
            company=company,
            email=DEV_EMAIL,
            full_name="Local Developer",
            password=secrets.token_urlsafe(24),
        )
    await grant_super_admin(session, company=company, user=user, meta=SYSTEM_META)
    await session.commit()
    return user


async def seed() -> None:
    settings = get_settings()
    if settings.environment != "local":
        sys.exit("Refusing to seed sample data outside ENVIRONMENT=local.")
    meta = SYSTEM_META
    async with get_sessionmaker()() as s:
        await bootstrap(s)
        company = await ensure_company(s, settings)
        if await s.scalar(
            select(Product.id).where(Product.company_id == company.id, Product.slug == MARKER_SLUG)
        ):
            print("Sample data already present; nothing to do.")
            return
        await register_initial_products(s)
        admin = await _admin(s, company)
        p = await load_principal(s, admin)

        staff = {}
        for name, email, role_slug in STAFF:
            user = await s.scalar(select(User).where(User.email == email))
            if user is None:
                user = await create_user(
                    s,
                    company=company,
                    email=email,
                    full_name=name,
                    password=secrets.token_urlsafe(24),
                )
                role = await s.scalar(
                    select(Role).where(Role.company_id == company.id, Role.slug == role_slug)
                )
                s.add(
                    UserRole(
                        user_id=user.id,
                        role_id=role.id,
                        scope_type="company",
                        granted_by_user_id=admin.id,
                    )
                )
            staff[role_slug] = user
        await s.commit()

        product = Product(
            company_id=company.id,
            name="Sample App (demo)",
            slug=MARKER_SLUG,
            category="Sample",
            tagline="A fictional product used to demonstrate Orbit.",
            lifecycle_status="beta",
            description="Sample data for local walkthroughs. Not a real Eranova product.",
            owner_user_id=admin.id,
            created_by_user_id=admin.id,
        )
        s.add(product)
        await s.flush()
        s.add(ProductStatusHistory(product_id=product.id, to_status="beta", reason="Sample data"))
        await s.commit()

        today = date.today()
        leads = []
        for i, (name, org, stage, follow) in enumerate(
            [
                ("Amina Otieno (sample)", "Lakeview Academy (sample)", "new", 0),
                ("Brian Kamau (sample)", "Riverside Hotel (sample)", "contacted", -2),
                ("Cynthia Wanjiru (sample)", "Hilltop School (sample)", "demo_scheduled", 3),
                ("David Mwangi (sample)", "Coastline Clinic (sample)", "negotiation", 1),
                ("Esther Njeri (sample)", "Greenfield College (sample)", "interested", 5),
            ]
        ):
            lead = await crm.create_lead(
                s,
                actor=admin,
                principal=p,
                meta=meta,
                payload=LeadCreate(
                    full_name=name,
                    email=f"lead{i}.sample@example.com",
                    organization=org,
                    product_id=product.id,
                    source=["website", "referral", "event"][i % 3],
                    owner_user_id=staff["sales"].id,
                    next_follow_up=today + timedelta(days=follow),
                ),
            )
            if stage != "new":
                await crm.update_lead(
                    s,
                    actor=admin,
                    principal=p,
                    lead_id=lead.id,
                    payload=LeadUpdate(status=stage),
                    meta=meta,
                )
            await crm.add_lead_activity(
                s,
                actor=admin,
                principal=p,
                lead_id=lead.id,
                meta=meta,
                payload=ActivityIn(
                    type="call", subject="Intro call (sample)", body="Discussed needs."
                ),
            )
            leads.append(lead)
        await crm.convert_lead(
            s,
            actor=admin,
            principal=p,
            lead_id=leads[3].id,
            meta=meta,
            payload=LeadConvert(customer_name="Coastline Clinic (sample)"),
        )
        other = await create_customer(
            s,
            admin,
            p,
            CustomerIn(
                name="Sunrise Primary (sample)",
                industry="Education",
                account_manager_user_id=staff["sales"].id,
            ),
            meta,
        )
        await upsert_subscription(
            s,
            admin,
            p,
            other.id,
            SubscriptionIn(
                product_id=product.id, plan_name="Standard", renewal_date=today + timedelta(days=20)
            ),
            meta,
        )

        project = await work.create_project(
            s,
            admin,
            p,
            ProjectIn(
                name="Sample App v2 launch (sample)",
                product_id=product.id,
                status="active",
                priority="high",
                manager_user_id=admin.id,
                start_date=today - timedelta(days=14),
                due_date=today + timedelta(days=30),
            ),
            meta,
        )
        await work.upsert_milestone(
            s,
            admin,
            p,
            project.id,
            MilestoneIn(title="Beta release", due_date=today + timedelta(days=10)),
            meta,
        )
        for title, who, due, prio in [
            ("Fix login timeout", "developer", -3, "high"),
            ("Write release notes", "marketing", 5, "medium"),
            ("Payment page redesign", "developer", 7, "critical"),
            ("Onboarding email sequence", "marketing", 12, "medium"),
            ("Update help centre articles", "support", -1, "low"),
            ("Load test the API", "developer", 9, "high"),
        ]:
            await work.create_task(
                s,
                admin,
                p,
                TaskIn(
                    project_id=project.id,
                    title=f"{title} (sample)",
                    priority=prio,
                    assignee_user_id=staff[who].id,
                    due_date=today + timedelta(days=due),
                ),
                meta,
            )

        for subject, prio, category, resolve in [
            ("Cannot reset password (sample)", "high", "account", False),
            ("Invoice shows wrong amount (sample)", "medium", "billing", False),
            ("Feature request: SMS reminders (sample)", "low", "feature_request", False),
            ("App slow in the morning (sample)", "urgent", "bug", True),
        ]:
            t = await support.create_ticket(
                s,
                admin,
                p,
                support.TicketIn(
                    subject=subject,
                    description="Reported by a sample customer.",
                    product_id=product.id,
                    customer_id=other.id,
                    requester_email="customer.sample@example.com",
                    priority=prio,
                    category=category,
                    assignee_user_id=staff["support"].id,
                ),
                meta,
            )
            await support.add_message(
                s, admin, p, t.id, support.MessageIn(body="Thanks, we're looking into it."), meta
            )
            if resolve:
                await support.transition(
                    s,
                    admin,
                    p,
                    t.id,
                    support.TransitionIn(
                        status="resolved", resolution="Added a database index (sample)."
                    ),
                    meta,
                )

        campaign = await marketing.create_campaign(
            s,
            admin,
            p,
            marketing.CampaignIn(
                name="Back-to-school launch (sample)",
                product_id=product.id,
                objective="Sign up 20 schools.",
                audience="Head teachers in Nairobi",
                channels=["facebook", "email", "whatsapp"],
                status="active",
                start_date=today - timedelta(days=5),
                end_date=today + timedelta(days=25),
                budget_amount="50000",
                budget_currency="KES",
                owner_user_id=staff["marketing"].id,
            ),
            meta,
        )
        await marketing.add_metric(
            s,
            admin,
            p,
            campaign.id,
            marketing.MetricIn(
                metric="Leads generated",
                value="12",
                source="Sample figure (not real)",
            ),
            meta,
        )
        marketer = staff["marketing"]
        mp = await load_principal(s, marketer)
        drafts = []
        for title, kind, channel in [
            ("Launch announcement (sample)", "announcement", "facebook"),
            ("Welcome email (sample)", "email", "email"),
            ("WhatsApp teaser (sample)", "social_caption", "whatsapp"),
        ]:
            drafts.append(
                await marketing.create_content(
                    s,
                    marketer,
                    mp,
                    marketing.ContentIn(
                        title=title,
                        kind=kind,
                        channel=channel,
                        campaign_id=campaign.id,
                        body="Sample copy for the demo. Replace with real content.",
                    ),
                    meta,
                )
            )
        await marketing.act_on_content(
            s, marketer, mp, drafts[1].id, marketing.ContentAction(action="submit"), meta
        )
        await marketing.act_on_content(
            s, marketer, mp, drafts[2].id, marketing.ContentAction(action="submit"), meta
        )
        await marketing.act_on_content(
            s, admin, p, drafts[2].id, marketing.ContentAction(action="approve"), meta
        )
        await marketing.act_on_content(
            s,
            marketer,
            mp,
            drafts[2].id,
            marketing.ContentAction(
                action="schedule", scheduled_for=datetime.now(UTC) + timedelta(days=2)
            ),
            meta,
        )

        await documents.upload(
            s,
            admin,
            p,
            documents.DocumentMeta(
                title="Leave policy (sample)",
                category="policy",
                description="Sample document for the demo.",
            ),
            "leave-policy-sample.txt",
            b"Sample leave policy. Not a real Eranova policy.\n",
            meta,
        )

        await integrations.create_connection(
            s,
            admin,
            p,
            integrations.ConnectionIn(
                provider="http_monitor",
                name="example.com uptime (sample)",
                product_id=product.id,
                config={"url": "https://example.com"},
                sync_interval_minutes=15,
            ),
            meta,
        )
        print(f"Sample data created. Sign-in is automatic locally as {admin.email}.")


async def _main() -> None:
    try:
        await seed()
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
