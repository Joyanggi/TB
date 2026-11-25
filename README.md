# 트바 (TrustBite)

트바(TrustBite) 앱의 기획·설계 문서와 개발 규칙을 담은 공개 GitHub 저장소(`Joyanggi/TB`)입니다. Claude Code와 Codex로 기획, 구현, 검증을 진행합니다.

## 시작하기

Orca의 **트바 마스터 열기**로 로컬 `main`을 연 뒤 **트바 마스터** 채팅에 `/orchestrate <하고 싶은 작업>`을 보냅니다. [마스터 열기와 다시 시작하기](docs/development/WORKFLOW.md#트바-마스터-열기)에 터미널 명령과 시작 프롬프트가 있습니다.

1. [Claude에게 보낼 시작 요청문](docs/development/CLAUDE-HANDOFF.md)에 앱 아이디어를 적고, Orca의 이 저장소에서 Claude Code를 열어 붙여넣습니다.
2. 요구사항과 첫 버전 범위를 확정하고, 개발 환경과 검증 계획을 정합니다.
3. Expo 프로젝트를 생성한 뒤 실행 명령을 이 README에 기록합니다.

개발은 Orca의 **Mac 로컬**에서 시작합니다. 기술 방향은 **Expo / React Native / TypeScript**, 첫 실기기 검증은 **iPhone**입니다. 앱 식별자는 `com.joyanggi.trustbite`로 확정했고, 첫 출시의 플랫폼 범위는 미정입니다.

## 문서와 개발 규칙

| 파일 | 용도 |
| --- | --- |
| [PRD](docs/product/PRD.md) · [요구사항](docs/product/REQUIREMENTS.md) | 어떤 문제를 풀고 무엇을 만들어야 하는지 |
| [아키텍처](docs/architecture/ARCHITECTURE.md) · [기술 결정 기록](docs/decisions/README.md) | 앱 구조와 주요 선택의 이유 |
| [테스트 전략](docs/quality/TEST-STRATEGY.md) · [위험 목록](docs/quality/RISK-REGISTER.md) · [실기기 체크리스트](docs/quality/RELIABILITY-CHECKLIST.md) | 무엇을 검증하고 어떤 증거를 남길지 |
| [개발 흐름](docs/development/WORKFLOW.md) · [리뷰 기준](REVIEW.md) · [커밋·이슈·PR 작성 규칙](docs/development/PR-ISSUE-GUIDE.md) | Orca, Git worktree, 검토와 GitHub 작성 양식 |
| [AGENTS.md](AGENTS.md) · [CLAUDE.md](CLAUDE.md) | Claude Code와 Codex가 공유하는 저장소 규칙 |

## 현재 상태

앱 이름은 **트바(TB, trustBite)**이며 기획·설계 문서 초안(v0.3)까지 작성된 단계입니다. 구현 승인 전이라 Expo 프로젝트, 앱 실행 명령, 실기기 테스트 결과는 아직 없습니다. 프로젝트를 생성한 뒤 실제 실행한 명령을 추가합니다.
