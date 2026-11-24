# 앱 아키텍처 — 트바(TB, trustBite)

- 상태: **초안 v0.3, Supabase 승인(ADR-001)** (2026-11-24). 담당자 요청으로 네이버 검색·지도, 소셜 로그인(Apple·Google·카카오·네이버), 최근 로그인 안내, 지도 포함, 앱 식별자를 반영했다. 나머지는 제안이며 구현·초기화는 승인 후 시작한다.
- 표기: [확정] 사용자 요청 · [제안] 승인 전 기본안 · [결정 필요] 답 필요 · [확인 필요] 초기화·구현 전에 공식 문서로 검증
- 관련: [PRD](../product/PRD.md) · [요구사항](../product/REQUIREMENTS.md) · [결정 기록](../decisions/README.md)

## 추천 기술 조합 [제안]

| 계층 | 선택 | 한 줄 이유 |
| --- | --- | --- |
| 앱 | Expo + React Native + TypeScript, Expo Router [확정: Expo·RN·TS] | Mac 로컬 개발, iPhone 먼저, Android 확장 가능 |
| 백엔드·DB·인증 | **Supabase**(Postgres + Auth + Row Level Security + Edge Functions) | 그룹별 접근 제어를 DB 정책으로, 랭킹은 SQL로 |
| 로그인 | 소셜 로그인 [확정]: Apple·Google(앱 내장 로그인 창 토큰 방식, 1단계) → 카카오·네이버(1b단계). Supabase Auth 세션 사용. 최근 로그인 수단은 기기 로컬에 저장해 안내 | [ADR-002](../decisions/002-로그인-방식.md) |
| 식당 검색 | **네이버 검색 API(지역 검색)**를 Edge Function으로 프록시 [확정: 네이버] | 키 비노출, 공급자 교체 가능. 결과 최대 5건 한계는 [ADR-003](../decisions/003-식당-검색과-지도-공급자.md) |
| 지도 | **네이버 지도**(`@mj-studio/react-native-naver-map`, 개발 빌드) [확정: 지도 포함, 구현 4단계] | Expo config plugin 제공, Expo Go 불가 |
| 위치 | `expo-location`(사용 중에만), 서버 RPC에서 거리 판정 | 클라이언트 위조 방지, 좌표 비저장 |
| 상태·서버 데이터 | TanStack Query + Supabase JS 클라이언트 | 캐시·재시도·무효화 |
| 테스트 | Jest(jest-expo) · Supabase DB 정책 테스트(pgTAP) | 정책·집계를 자동으로 검증 |

### 선택 이유 (비용 · 유지보수 · 그룹 접근 제어 · 국내 식당 검색 품질)

네이버 검색·지도, 소셜 로그인, 지도 포함은 담당자 요청으로 확정했고, 아래는 나머지(백엔드)의 이유와 확정된 선택의 한계다.

| 기준 | Supabase + 네이버 | 대안: Firebase | 대안: 직접 만든 서버 |
| --- | --- | --- | --- |
| 비용 | 개발은 무료 요금제로 가능([확인 필요]: 2026-11 조사에서 활성 프로젝트 2개, DB 500MB, 비활성 1주 시 일시 중지, 출처마다 MAU 수치 상이). 베타부터 Pro(월 $25 수준 [확인 필요]) 권장. 네이버 검색 일 25,000회 [확인 필요], 지도 과금·쿼터는 [확인 필요] | Firestore는 읽기 단위 과금이라 랭킹 화면 1회가 평가 수만큼 읽기로 청구될 수 있음 | 서버 호스팅·운영 인건비 |
| 유지보수 | 관리형. SQL 마이그레이션 파일로 변경 이력, 서버 코드는 Edge Function 1~2개 | 관리형이나 집계를 클라이언트나 별도 함수에 구현해야 함 | 인증·배포·모니터링을 모두 직접 |
| 그룹별 접근 제어 | **DB 정책이 행 단위로 멤버십을 검사**. 클라이언트 버그가 있어도 비멤버가 읽을 수 없고, 정책을 자동 테스트로 검증 가능 | 보안 규칙으로 가능하나 "멤버 전원의 평가 평균" 같은 조인·집계가 어려움 | 가능하나 정책 누락 위험을 직접 관리 |
| 국내 식당 검색 | 네이버: 지역 검색 응답에 좌표 포함(문서 확인). 국내 장소 coverage 수준은 G3에서 검증 [확인 필요]. **단, 지역 검색은 결과 최대 5건·페이지 없음·반경/카테고리 필터 없음** → 후보 UX와 주변 탐색 범위에 제약(대응은 ADR-003) | (검색은 어느 쪽이든 외부 공급자) | 동일 |

랭킹이 핵심 기능이고 랭킹은 "여러 사용자의 행을 범위별로 묶어 평균"하는 관계형 질의이므로 Postgres가 가장 자연스럽다.

**네이버 선택의 약점과 대응**: ① 검색이 5건이라 동명이점 후보가 부족할 수 있다 → 지역명 조합 검색·안내, 단계 0 스파이크에서 품질 검증. ② 장소 고유 ID가 없다 → 이름+주소 해시 키. ③ 지도 라이브러리가 커뮤니티 유지이며 개발 빌드·New Architecture 전용이다 [확인 필요: 현재 버전] → 버전 고정, 업그레이드 전 스모크. ④ 검색 결과의 저장·표시 약관이 확인되지 않았다 → 구현 전 게이트(ADR-003 G1~G2). 상세는 [ADR-003](../decisions/003-식당-검색과-지도-공급자.md).

## 앱 구성 [제안]

### 화면

```
(인증)  소셜 로그인(Apple·Google → 1b: 카카오·네이버), "최근 사용" 표시
(탭)
  ├ 랭킹     범위 선택(내 랭킹 / 그룹…) → 순위 목록 → 식당 상세·내 평가
  ├ 찾기     검색 → 후보 → 식당 요약 → 평가 작성
  ├ 그룹     그룹 목록 → 그룹 상세(멤버·초대) → 그룹 만들기
  └ 설정     계정·로그아웃·계정 삭제·위치 권한 안내
(딥링크)  /join/<토큰> → 로그인(필요 시) → 그룹 참여 확인
```

### 폴더 구조 (초기화 시 생성기 구조를 확인한 뒤 확정 [확인 필요])

```
app/                     Expo Router 화면
src/features/{auth,search,review,ranking,groups,verification}/
src/lib/{supabase,query}/
supabase/migrations/     스키마·정책·함수 (SQL)
supabase/functions/place-search/
supabase/tests/          DB 정책·집계 테스트
```

## 데이터 설계

### 개체와 관계

```
auth.users ─1:1─ profiles(id, display_name)
groups(id, name, kind[group|couple], max_members, created_by)
group_members(group_id, user_id, role[admin|member], joined_at)   PK(group_id, user_id)
group_invites(id, group_id, token_hash, expires_at, max_uses, used_count, revoked_at)
restaurants(id, provider[naver], provider_place_key, provider_place_key_version, name, address, road_address,
            lat, lng, category, coord_source, coord_updated_at)     UNIQUE(provider, provider_place_key)
reviews(id, user_id, restaurant_id, group_id NULL,
        taste, value, mood [1..5], tags[], client_request_id,
        visit_verified, verification_status, verified_at, verification_rule_version,
        created_at, updated_at)                                     UNIQUE(user_id, client_request_id)
place_candidates(id, user_id, payload, expires_at)               서버 전용 임시 보관(클라이언트 접근 없음)
```

핵심 설계 결정:

1. **식당의 고유 ID**: 앱 자체의 `restaurants.id`(uuid). 외부 공급자의 `(provider, provider_place_key)`를 유니크 키로 두어 같은 장소는 한 행, 이름이 같아도 주소가 다르면 다른 행(동명이점 구분). **네이버 지역 검색에는 장소 고유 ID가 없으므로** `provider_place_key`는 정규화한 (이름 + 도로명 주소)의 해시로 직접 만든다(키 규칙은 [ADR-003](../decisions/003-식당-검색과-지도-공급자.md)). 공급자를 바꾸거나 키 규칙을 보정해도 `restaurants.id`와 평가는 유지하고 `provider` 열로 매핑한다.
2. **식당 행은 사용자가 선택할 때만, 서버만 쓴다**: 검색 Edge Function은 공급자 응답을 서버 전용 테이블 `place_candidates`(사용자 ID, 공급자 원본 필드, 만료 10분)에 저장하고 후보 ID와 표시 정보를 반환한다. 이 테이블은 RLS를 켜고 정책을 두지 않아 클라이언트가 읽거나 쓸 수 없고, 만료된 행은 주기적으로 삭제한다. 사용자가 후보를 선택하면 `select_place(candidate_id)`가 **호출자와 후보의 사용자 ID 일치·만료 전 여부**를 검사한 뒤 서버에 저장된 원본으로 `restaurants`를 upsert하고, 식당 ID와 표시 정보(이름·주소·좌표·카테고리)를 반환한다. 같은 후보를 다시 선택하면 같은 식당 ID를 반환한다(멱등). 클라이언트가 보낸 이름·좌표는 쓰지 않으므로 위조할 수 없고, 선택하지 않은 후보는 `restaurants`에 저장되지 않는다. `place_candidates`는 공급자 응답을 짧게 임시 보관하므로 약관상 허용되는지 ADR-003 G1에서 확인한다 [확인 필요]. `place-search`와 `select_place`는 모두 사용자별 호출 제한을 둔다.
3. **평가는 방문 1회 = 1행**. 재방문은 새 행(요청 ID가 다름). `group_id`가 NULL이면 개인 평가, 값이 있으면 그 그룹에 속한 평가. 한 평가는 최대 한 그룹에 속한다([ADR-004](../decisions/004-랭킹-집계와-그룹-평가-연결.md), Q1 확정).
4. **중복 방지**: `UNIQUE(user_id, client_request_id)` + 저장 RPC가 충돌 시 기존 행을 반환(멱등).
5. **방문 인증은 평가의 속성**: `reviews`의 열이며 별도 위치 테이블이 없다. 배지는 평가 단위이므로 그룹원에게 노출하는 쿼리에서 제외한다.
6. **랭킹은 저장하지 않고 계산**: 뷰/RPC로 매번 집계(평가 수가 작은 첫 버전). 수정·삭제가 즉시 반영되고 불일치가 생기지 않는다. 성능 문제가 생기면 머티리얼라이즈드 뷰를 [재검토 조건](../decisions/004-랭킹-집계와-그룹-평가-연결.md)에 따라 도입.

### 접근 제어 (Row Level Security) [제안]

| 테이블 | 읽기 | 쓰기 |
| --- | --- | --- |
| profiles | 본인 + 같은 그룹 멤버의 표시 이름만 | 본인 |
| groups, group_members | 그 그룹의 현재 멤버 | 직접 쓰기 없음. `create_group`, `leave_group` 등 RPC |
| group_invites | 그룹 관리자의 목록 조회. 테이블 전체 SELECT를 부여하지 않고 `token_hash`를 뺀 열에만 SELECT 부여(어떤 클라이언트 역할도 해시를 읽을 수 없음) | 함수로만 생성(그룹 멤버)·폐기(생성자·그룹 관리자) |
| restaurants | 사용자가 평가했거나 자기가 볼 수 있는 평가가 가리키는 식당만(그 밖의 행은 직접 조회 불가) | `select_place` 함수(서버)만 |
| reviews | `authenticated`는 **공개 열**(`id`, `user_id`, `restaurant_id`, `group_id`, `taste`, `value`, `mood`, `tags`, `created_at`, `updated_at`)만 SELECT하며, 행은 (작성자 본인) 또는 (`group_id`가 있고 호출자와 작성자가 모두 그 그룹의 현재 멤버)일 때만 보인다. **작성자 전용 열**(`client_request_id`, `visit_verified`, `verification_status`, `verified_at`, `verification_rule_version`)은 base 테이블의 SELECT 권한을 회수하고 `my_reviews` 뷰(`auth.uid() = user_id` 필터)로만 읽는다 | `authenticated`에는 INSERT·UPDATE 권한이 없다(`submit_review`, `update_review` 함수만 쓴다). DELETE는 작성자 본인만 |

- 멤버 판정은 `is_group_member(gid)` 보안 정의 함수(정책 재귀 방지). **모든 `SECURITY DEFINER` 함수는 `search_path`를 고정하고 `anon`·`public`의 실행 권한을 회수**하며, JWT의 `auth.uid()`와 사용자 존재를 검사한다(삭제된 계정의 만료 전 토큰 차단, F-002).
- **열 권한은 역할 단위이고 RLS는 행 단위**라서 같은 `authenticated` 역할인 작성자와 다른 멤버를 구분하는 일은 뷰(`my_reviews`)와 함수가 한다. 작성자 전용 열을 이름으로 직접 SELECT하면 권한 오류(permission denied)다.
- **탈퇴한 멤버의 평가**: 작성자 본인은 계속 읽을 수 있지만(내 랭킹) 그룹 정책의 읽기 조건은 작성자의 **현재** 멤버십을 요구하고, `get_ranking`의 그룹 범위는 호출자와 집계 대상 양쪽의 현재 멤버십을 모두 확인한다.
- **내 랭킹 질의는 `user_id = auth.uid()`를 명시**해야 한다. 정책상 다른 멤버의 그룹 평가도 읽을 수 있으므로 정책만 믿고 개인 랭킹을 계산하면 남의 평가가 섞인다(테스트 항목).
- 서비스 키는 서버(Edge Function) 환경변수에만 두고 앱에는 공개 키(anon)만 넣는다.

### 주요 함수 [제안]

| 함수 | 역할 |
| --- | --- |
| `place-search` (Edge Function) | 입력 분류, 공급자 호출, 결과를 `place_candidates`에 임시 저장하고 후보 ID와 표시 정보 반환. JWT 검증과 사용자별 호출 제한, `restaurants`에는 저장하지 않음 |
| `select_place(candidate_id)` | 후보의 사용자 ID·만료를 검사한 뒤 서버에 저장된 원본으로 `restaurants`를 upsert하고 식당 ID와 표시 정보를 반환(재선택은 멱등, 사용자별 호출 제한). 클라이언트가 보낸 이름·좌표는 사용하지 않음 |
| `submit_review(restaurant_id, group_id, scores, tags, request_id, location?)` | 멤버십·점수 검증, 멱등 저장, 방문 인증 판정(좌표는 저장하지 않음) |
| `update_review(review_id, scores, tags)` | 작성자 본인의 점수·태그 수정(그룹·배지·판정 열 변경 불가) |
| `get_ranking(scope_type, group_id?)` | 범위별 순위 집계(호출자 권한으로 실행해 정책 적용) |
| `create_group`, `create_invite`, `preview_invite`, `accept_invite`, `leave_group` | 그룹 수명주기. 초대 토큰은 128비트 무작위이며 서버에는 해시만 저장. `preview_invite`는 유효한 토큰에 한해 그룹 이름만 반환하고 `accept_invite`는 정원·사용 횟수·멤버 추가를 한 트랜잭션으로 처리. 두 함수 모두 사용자별 호출 제한을 두고 존재하지 않는 값은 모두 같은 "사용할 수 없는 초대"로 응답 |
| `delete_account` (Edge Function) | 요청 본문의 사용자 ID는 받지 않고 **서버가 JWT를 검증(`auth.getUser`)해 확인한 본인만** 삭제하며 최근 재인증(로그인 후 N분 이내)을 요구한다 [제안]. 순서: ①제공자 연결 해제(Apple 토큰 해지 등) → ②앱 데이터·멤버십 정리(마지막 멤버면 그룹 삭제, 유일한 관리자면 가장 오래된 멤버가 관리자 승계) → ③Auth 사용자 삭제. 각 단계는 멱등이라 중간에 실패해도 같은 요청을 재시도하면 이어서 끝나고 응답을 잃어도 성공으로 끝난다. 삭제 뒤 만료 전 JWT는 함수가 사용자 존재를 검사해 거부한다 |

## 로그인과 계정

[ADR-002](../decisions/002-로그인-방식.md) 기준 요약이다.

| 제공자 | 단계 | 방식 | 비고 |
| --- | --- | --- | --- |
| Apple | 1 | 기기 내장 로그인 → 토큰을 Supabase에 전달 | iOS 필수 병행, 이메일 가림 주소 가능 |
| Google | 1 | 기기 내장 로그인 → 토큰을 Supabase에 전달 | iOS·Android 클라이언트 설정 |
| 카카오 | 1b | Supabase 기본 제공 방식(브라우저 로그인 후 앱으로 복귀)을 우선 검토 | 앱 내장 SDK 토큰 방식은 확인되지 않음 [확인 필요] |
| 네이버 | 1b | 앱이 받은 인가 코드를 서버(Edge Function)가 client secret으로 교환해 우리 앱용 토큰임을 증명 → 제공자 사용자 ID로 사용자 조회·생성 → 세션 발급 [확인 필요: 발급 수단] | Supabase 기본 제공 아님, **세션을 발급하는 보안 민감 코드**라 독립 리뷰 필수. 이메일로 사용자 연결 금지 |

- 계정 ID는 `auth.users.id`. 제공자 종류를 바꿔 로그인하면 이메일이 같더라도 **별도 계정**(첫 버전 제안, 계정 합치기는 후속). Supabase의 같은 이메일 자동 연결 동작을 확인하고 필요하면 끄거나 우회한다(ADR-002 G6). 제공자가 이메일을 주지 않거나 가린 경우에도 동작해야 한다.
- **최근 로그인 수단 안내(F-051)**: 로그인 성공 시 제공자 종류(`provider`)만 기기에 저장한다(보안 저장소 후보 `expo-secure-store`, 일반 설정 저장소는 [확인 필요]). 로그아웃·세션 만료에서도 지우지 않고 계정 삭제 때만 지운다. 시각·이메일·토큰·사용자 ID는 저장하지 않는다. 계정 삭제는 서버 삭제가 성공한 뒤에만 지운다. 저장값이 없거나 읽기에 실패하면 안내 문구만 바꾸고 로그인은 막지 않는다. 이 기록은 **기기 단위**이므로 새 기기·앱 삭제(저장소 유지 여부는 OS에 따라 다름 [확인 필요]) 뒤에는 없을 수 있고, 그때를 위한 일반 안내를 둔다. 서버가 이메일로 가입 수단을 알려 주는 방식은 계정 존재가 노출되어 제외했다.
- 계정 삭제(F-002)는 앱 데이터 삭제와 함께 제공자별 연결 해제(Apple 토큰 해지 등)를 수행한다 [확인 필요].

## 위치 인증 처리

[PRD 방문 인증](../product/PRD.md#c-방문-인증-확정) 요구를 아래 방식으로 구현한다([ADR-005](../decisions/005-방문-인증-처리와-위치-정보-최소화.md)).

흐름: 평가 저장 탭 → (첫 1회 안내) → OS 권한 "앱 사용 중 허용" → 현재 위치 1회 측정(타임아웃 10초) → `submit_review`에 `{lat, lng, accuracy, age_ms}`(`age_ms`는 측정 후 경과 시간)를 **일회성 인자**로 전달 → 서버가 거리 계산·판정 → 결과만 저장.

| 정보 | 처리 | 보관 |
| --- | --- | --- |
| 원본 좌표(위도·경도) | 판정에만 사용 | **보관·로그 안 함** |
| 정확도(m) | 판정 조건(≤100m [제안]) | 보관 안 함 |
| 측정 경과 시간 | 판정 조건(측정 후 60초 이내 [제안]). 클라이언트 시계 대신 앱이 보고하는 경과 초와 서버 수신 시각으로 계산 | 보관 안 함 |
| 식당 좌표 | 공급자 제공 좌표 | 보관(`restaurants.lat/lng`), 출처를 `coord_source`(provider, 조회 시각)로 기록 |
| 판정 결과 | `visit_verified`, `verification_status`(verified·out_of_range·permission_denied·low_accuracy·stale·no_coordinates·unavailable) | 보관(평가 행) |
| 판정 시각·기준 버전 | 기준 변경 시 과거 결과 해석용 | 보관(`verified_at`, `verification_rule_version`) |

- 거리 계산: 구면 거리(하버사인, 지구 반경 6,371km). 경계 처리: **거리 ≤ 200.0m → 인증**. 서버 SQL 함수 하나에서만 계산해 테스트한다.
- 백그라운드 위치·지오펜싱 없음. iOS는 `NSLocationWhenInUseUsageDescription`만 사용(한국어 목적 문구).
- 한계: 위치 위조는 완전히 막을 수 없다(특히 앱 변조). 배지는 보안 인증이 아니라 UX 신호이며 점수 가중치로 쓰지 않는 이유다.

## 검색 흐름 [제안]

```
앱 입력 → (debounce 500ms, 이전 요청 취소) → place-search(query, anchor?)
   서버: 네이버 지역 검색 호출(최대 5건, 제목 태그 제거) → type 판정(area|place) → place면 후보 [{candidateId,name,address,category,distance?}] 반환(저장하지 않음). 후보 선택 시 `select_place`가 식당 upsert 후 restaurantId 반환
앱: place → 후보 목록 / area → "‘○○’ 주변으로 이동" 행 / 빈 결과 → 메시지 / 실패 → 다시 시도
확정(탭 또는 키보드 검색 키): place → 평가 화면, area → 검색 기준 위치 변경 후 주변 식당
```

타이핑만으로는 기준 위치나 선택이 바뀌지 않는다. 서버에 분류를 두는 이유는 공급자 키 비노출, 쿼터 관리(캐싱 가능 여부는 약관 확인 후), 공급자 교체 시 앱 변경 최소화다.

## 앱 식별자 [확정]

| 항목 | 값 | 비고 |
| --- | --- | --- |
| 앱 표시 이름 | **트바** (영문 보조: TB, trustBite) | 홈 화면 표기는 8자 이내가 안전 |
| iOS bundle identifier | **`com.joyanggi.trustbite`** (2026-11-24 추천안 승인) | 스토어 등록 후 변경 불가. 대체안 `app.trustbite.tb`, `kr.co.trustbite.app`은 도메인 소유 시에만 |
| Android package name | **`com.joyanggi.trustbite`** (iOS와 동일) | 출시 후 변경 불가. Android 출시 여부·일정은 미정 |
| URL scheme | `trustbite` | 초대 딥링크 `trustbite://join/<토큰>` |

도메인을 소유하면 유니버설 링크/앱 링크로 `https://…/join/<토큰>`을 쓸 수 있다(카카오톡 등 메신저에서 링크 탭이 앱으로 연결되는 품질이 높음). 없으면 커스텀 스킴 + 초대 코드 직접 입력을 병행한다.

## 플랫폼 [확정/제안]

- Orca **Mac 로컬**에서 개발, iPhone 실기기 먼저 검증 [확정]. Android 지원은 고려하되 **동시 출시 여부·일정은 미정** [확정]. 첫 구현에서는 Android 빌드와 핵심 흐름 스모크 확인만 목표로 둔다 [제안].
- Expo SDK·React Native·Node·패키지 관리자 버전은 **초기화 시점에 공식 문서와 로컬 환경에서 호환 확인**한다([확인 필요]). 2026-11 조사에서는 Expo SDK 58(2026-10 출시)이 최신으로 보였으나 확정값이 아니다.
- 네이버 지도, 소셜 로그인, 위치, 딥링크 때문에 Expo Go가 아닌 **개발 빌드가 필요하다**(네이버 지도 라이브러리는 개발 빌드 전용, New Architecture 전용). 단계 0 스파이크에서 Expo SDK·지도 라이브러리·로그인 모듈이 한 개발 빌드에서 함께 빌드되는지 먼저 확인한다. 첫 실기기 빌드 직전 iPhone 연결과 Apple Developer 계정 상태(개인 기기 설치용 무료 프로비저닝은 설치 만료 주기가 짧음, TestFlight는 유료 프로그램 필요)를 확인한다.

## 권한과 개인정보

| 권한/데이터 | 요청 시점 | 이유 | 거부 시 | 처리 |
| --- | --- | --- | --- | --- |
| 위치(사용 중) | 첫 평가 저장 | 방문 인증 | 배지 없이 저장 | 서버 판정 후 폐기 |
| 최근 로그인 수단(제공자 종류만) | 로그인 성공 | 재방문 시 안내 | 안내 없이 일반 문구 | 기기 로컬 저장, 서버 전송 없음 |
| 소셜 계정 정보(이름·이메일 등 제공자가 주는 값) | 로그인 | 계정·복구 | 로그인 불가 | 인증 공급자(Supabase Auth)에 저장, 그룹원에게는 표시 이름만 노출 |
| 알림·카메라·연락처·사진 | 요청 안 함 | — | — | — |

## 빌드·설정

- 환경변수: 앱에는 `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY`만 [확인 필요: 이름은 초기화 시 확정]. 네이버 검색 키와 서비스 키는 Supabase 비밀(secrets)에만. 네이버 지도 클라이언트 ID와 소셜 로그인 클라이언트 ID는 앱 설정에 포함(앱 식별자에 묶이므로 식별자 확정 후 발급). `.env`는 저장소 밖 또는 `.gitignore` 대상.
- 개발용 Supabase 프로젝트는 호스팅 프로젝트를 우선한다(로컬 Supabase는 Docker를 요구해 맥 자원 부담). 마이그레이션은 SQL 파일로 저장소에 보관.
- 소셜 로그인 설정: Apple Developer Program, Google·카카오·네이버 앱 등록은 앱 식별자(확정) 기준으로 진행하며 비용·심사가 필요한 단계는 시작 직전에 확인한다. 개인별 키·인증서는 저장소 밖에서 관리한다.

## 배포 [제안]

- 1차: iPhone 개발 빌드(직접 설치) → TestFlight 내부 테스트 → 필요 시 외부 베타. 앱스토어 제출은 이번 범위 밖.
- 장애 복구: 서버 변경은 마이그레이션 파일로 되돌리거나 새 마이그레이션으로 수정. 검색 공급자 장애 시 검색만 실패하고 내 랭킹·평가 조회는 동작(검색과 랭킹의 의존 분리). 방문 인증 판정 실패는 평가 저장을 막지 않는다.
