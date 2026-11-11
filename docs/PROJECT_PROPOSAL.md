# Project Proposal: Splitmate

## 1. Project Overview

Splitmate is a web and mobile application designed to help groups manage shared expenses, balances, payments, notes, and tasks in one organized place. The system supports roommates, friends, travel groups, clubs, and small teams who need a simple way to track who paid, who owes whom, and what still needs to be completed.

The project includes a Flask-based backend, a browser-based web interface, and a cross-platform mobile app built with Expo and React Native. Splitmate combines expense splitting, task coordination, group notes, user authentication, email notifications, and optional payment support into a single collaborative platform.

## 2. Problem Statement

Managing shared costs manually can become confusing when multiple people contribute different amounts, split expenses unevenly, or forget to settle balances. Groups often rely on messages, spreadsheets, memory, or separate apps for payments, tasks, and notes. This can lead to missed repayments, unclear records, duplicated work, and disagreements about group finances.

Splitmate addresses this problem by providing a centralized system where users can create groups, record expenses, choose how each expense should be split, view balances, track payments, and manage related group tasks and notes.

## 3. Project Objectives

The main objectives of Splitmate are to:

- Provide a secure user account system with registration, login, email verification, and password reset.
- Allow users to create and manage groups for shared expenses and collaboration.
- Support multiple expense-splitting methods, including equal splits, exact amount splits, and percentage-based splits.
- Show clear balance summaries so group members can understand who owes money and who should receive money.
- Maintain transaction history for transparency and future reference.
- Allow manual payment records and optional online payment support through Stripe.
- Support group productivity through shared notes, tasks, due dates, and reminders.
- Provide both web and mobile access for convenient use across devices.
- Include admin tools for user monitoring, growth tracking, and reminder email controls.

## 4. Target Users

Splitmate is intended for:

- Roommates sharing rent, utilities, groceries, and household expenses.
- Friends planning trips, events, or group purchases.
- Students working on shared living or group activity budgets.
- Small clubs or teams that need lightweight expense and task coordination.
- Families or informal groups that want simple records of shared spending.

## 5. Proposed Solution

The proposed solution is a full-stack application with a Flask backend that manages users, groups, expenses, balances, notes, tasks, payments, and administrative functions. The backend exposes routes for the web interface and mobile API endpoints for the React Native app.

The web application provides browser-based access using Flask templates, HTML, CSS, and JavaScript. The mobile application uses Expo and React Native to provide a native-style experience on iOS and Android, including local task reminder notifications.

The application will store data using SQLAlchemy models and can run locally with SQLite during development. PostgreSQL support can be used for production deployment and scalability.

## 6. Key Features

### 6.1 User Management

- User registration and login.
- Secure password handling.
- Email verification using OTP.
- Forgot password and reset password workflow.
- Session-based web authentication and token-based mobile authentication.

### 6.2 Group Management

- Create and join groups.
- Add and manage group members.
- Organize expenses, notes, tasks, payments, and histories by group.

### 6.3 Expense Splitting

- Add expenses with description, amount, payer, and group members.
- Split expenses equally among selected members.
- Split expenses by exact amount.
- Split expenses by percentage.
- View recent expenses and transaction history.

### 6.4 Balances and Payments

- Display balance summaries for group members.
- Track outstanding amounts.
- Record manual payments between members.
- Support optional Stripe Checkout payment processing when configured.

### 6.5 Notes and Tasks

- Create shared notes for each group.
- Create tasks with due dates and reminder times.
- Mark notes and tasks as completed.
- Schedule local mobile notifications for task reminders.

### 6.6 Admin Dashboard

- View user growth and activity.
- Identify inactive users.
- Send or manage inactivity reminder emails.
- Monitor application-level usage.

## 7. Technology Stack

| Layer | Technology |
| --- | --- |
| Backend | Python, Flask |
| Database ORM | Flask-SQLAlchemy |
| Authentication | Flask-Login, token-based mobile auth |
| Database | SQLite for development, PostgreSQL-ready configuration |
| Web UI | Jinja templates, HTML, CSS, JavaScript |
| Mobile App | Expo, React Native, TypeScript |
| Notifications | Expo Notifications, APScheduler for backend jobs |
| Payments | Stripe SDK |
| Email | Gmail SMTP or compatible SMTP provider |
| Migrations | Flask-Migrate, Alembic |

## 8. Scope of Work

### In Scope

- Designing and implementing the web application.
- Designing and implementing the mobile application.
- Building backend data models for users, groups, expenses, payments, notes, and tasks.
- Implementing authentication, email verification, and password reset.
- Supporting multiple split methods.
- Creating balance and transaction history views.
- Supporting task reminders and notification registration.
- Providing admin dashboard functionality.
- Preparing local setup documentation and deployment-ready configuration.

### Out of Scope

- Direct bank account transfers.
- Advanced accounting reports for businesses.
- Multi-currency conversion with live exchange rates.
- Public social features outside group membership.
- Full production hosting, unless added as a separate deployment phase.

## 9. System Architecture

Splitmate follows a client-server architecture:

- The Flask backend handles business logic, database operations, authentication, email workflows, scheduled jobs, and payment integration.
- The web client uses server-rendered templates for browser access.
- The mobile client communicates with the backend through mobile API endpoints.
- The database stores persistent records for users, groups, expenses, payments, notes, tasks, and histories.
- Optional third-party services include Stripe for payment checkout and SMTP for email delivery.

## 10. Development Methodology

The project will use an iterative development approach. Core features will be developed first, followed by mobile support, admin tools, payment integration, testing, and documentation. Each phase will focus on a usable milestone so that the application can be tested continuously and improved based on feedback.

## 11. Project Timeline

| Phase | Duration | Activities |
| --- | --- | --- |
| Phase 1: Planning and Requirements | 1 week | Confirm goals, define user roles, identify core workflows, review technical requirements. |
| Phase 2: Backend Foundation | 2 weeks | Build Flask app structure, database models, authentication, group management, and environment configuration. |
| Phase 3: Expense and Balance Features | 2 weeks | Implement expense creation, split methods, balances, transaction history, and manual payments. |
| Phase 4: Notes, Tasks, and Notifications | 1 week | Add group notes, task management, due dates, reminders, and notification support. |
| Phase 5: Mobile Application | 2 weeks | Build Expo app screens, mobile authentication, API integration, task reminders, and settings. |
| Phase 6: Admin and Payment Support | 1 week | Add admin dashboard, inactivity reminders, and optional Stripe payment support. |
| Phase 7: Testing, Documentation, and Final Review | 1 week | Test major workflows, fix issues, update documentation, and prepare final delivery. |

Estimated total duration: 10 weeks.

## 12. Deliverables

The expected deliverables are:

- A functioning Flask web application.
- A functioning Expo React Native mobile application.
- Database models and migration support.
- User authentication and email verification workflows.
- Group expense splitting, balances, payments, notes, and tasks.
- Admin dashboard and reminder controls.
- Local setup documentation.
- Environment configuration guidance.
- Final project documentation and demonstration materials.

## 13. Testing and Evaluation

The project will be evaluated using the following criteria:

- Users can register, verify email, log in, and reset passwords successfully.
- Users can create groups and manage members.
- Expenses calculate correctly for equal, exact amount, and percentage splits.
- Balance summaries accurately reflect expenses and payments.
- Notes and tasks can be created, updated, completed, and displayed by group.
- Mobile app screens communicate correctly with the backend API.
- Reminder notifications and email flows work when configured.
- Admin dashboard displays useful user and activity information.
- Sensitive configuration values remain outside version control.

## 14. Risks and Mitigation

| Risk | Mitigation |
| --- | --- |
| Incorrect split calculations | Test each split method with multiple group sizes and edge cases. |
| Email setup issues | Provide clear SMTP environment variable documentation and fallback error handling. |
| Payment integration complexity | Keep Stripe optional and allow manual payment records as the default workflow. |
| Mobile API connectivity issues | Allow configurable API URLs and document LAN IP setup for Expo testing. |
| Data privacy concerns | Keep secrets in environment variables and avoid committing private database or credential files. |
| Scope expansion | Separate core features from future enhancements and prioritize required workflows first. |

## 15. Future Enhancements

Possible future improvements include:

- Multi-currency expense support.
- Automatic settlement suggestions.
- Receipt image uploads.
- Push notifications from the backend.
- Group invitation links.
- Exportable reports in CSV or PDF format.
- Dark mode for web and mobile interfaces.
- Production deployment with PostgreSQL and cloud hosting.

## 16. Conclusion

Splitmate provides a practical solution for groups that need a clear and reliable way to manage shared expenses and responsibilities. By combining expense splitting, balances, payments, notes, tasks, reminders, and cross-platform access, the project reduces confusion and improves accountability among group members.

The proposed system is technically achievable with the selected stack and can be developed in phases, making it suitable for academic, portfolio, or real-world small-group use.
