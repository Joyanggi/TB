# Mobile App Starter

앱 아이디어를 정한 뒤 Claude Code와 Codex로 기획, 구현, 검증을 시작하기 위한 비공개 저장소입니다. `mobile-app-starter`는 GitHub 저장소의 임시 이름입니다.

## 시작하기

1. [Claude에게 보낼 시작 요청문](docs/development/CLAUDE-HANDOFF.md)에 앱 아이디어를 적고, Orca의 이 저장소에서 Claude Code를 열어 붙여넣습니다.
2. 요구사항과 첫 버전 범위를 확정하고, 개발 환경과 검증 계획을 정합니다.
3. Expo 프로젝트를 생성한 뒤 실행 명령을 이 README에 기록합니다.

개발은 Orca의 **Mac 로컬**에서 시작합니다. 기술 방향은 **Expo / React Native / TypeScript**, 첫 실기기 검증은 **iPhone**입니다. 첫 출시의 플랫폼 범위와 앱 식별자는 제품을 정할 때 확정합니다.

## 문서와 개발 규칙

| 파일 | 용도 |
| --- | --- |
| [PRD](docs/product/PRD.md) · [요구사항](docs/product/REQUIREMENTS.md) | 어떤 문제를 풀고 무엇을 만들어야 하는지 |
| [아키텍처](docs/architecture/ARCHITECTURE.md) · [기술 결정 기록](docs/decisions/README.md) | 앱 구조와 주요 선택의 이유 |
| [테스트 전략](docs/quality/TEST-STRATEGY.md) · [위험 목록](docs/quality/RISK-REGISTER.md) · [실기기 체크리스트](docs/quality/RELIABILITY-CHECKLIST.md) | 무엇을 검증하고 어떤 증거를 남길지 |
| [개발 흐름](docs/development/WORKFLOW.md) · [리뷰 기준](REVIEW.md) | Orca, Git worktree, PR 검토 |
| [AGENTS.md](AGENTS.md) · [CLAUDE.md](CLAUDE.md) | Claude Code와 Codex가 공유하는 저장소 규칙 |

현재는 문서 초기화 단계입니다. Expo 프로젝트, 앱 실행 명령, 실기기 테스트 결과는 프로젝트를 생성한 뒤 추가합니다.
