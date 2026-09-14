/**
 * 제출 한 건을 처리한다.
 *
 * 구글 폼은 업로드된 파일을 질문별 폴더 하나에 전부 쏟아붓는다.
 * 이 함수가 그것을 <루트>/<주차>/<학번_이름>/ 으로 옮긴다.
 *
 * 설치형 트리거로 폼에 걸린다 (설치.gs 의 트리거설치()).
 * 트리거이므로 여기서 던진 예외는 아무 데도 보이지 않는다.
 * 그래서 모든 오류를 잡아 메일로 알리고, 파일은 원래 자리에 남긴다.
 */
function onSubmit(e) {
  const 응답 = e.response;
  try {
    const r = 정리(응답);
    기록(['성공', r.주차, r.학생, r.옮긴것.length, r.옮긴것.join(' | '), '']);
  } catch (err) {
    기록(['실패', '', '', 0, '', String(err)]);
    알림(
      '[과제수집] 제출 처리 실패',
      '제출 시각: ' + 응답.getTimestamp() + '\n\n' +
      '오류: ' + err + '\n\n' +
      '파일은 폼이 만든 기본 폴더에 그대로 있다. 잃어버린 것은 없다.\n' +
      '원인을 고친 뒤 설치.gs 의 밀린것처리() 를 돌리면 뒤늦게 정리된다.');
  }
}

/**
 * 응답 하나의 파일을 제자리로 옮긴다.
 *
 * 여러 번 돌려도 결과가 같다 — 이미 옮긴 파일은 건너뛰고,
 * 이미 시각이 붙은 이름에는 다시 붙이지 않는다.
 * 밀린것처리() 가 이 성질에 기댄다.
 */
function 정리(응답) {
  const 항목 = 응답.getItemResponses();
  const 주차명 = 주차확인(값(항목, Q.주차));
  const 폴더명 = 폴더이름(값(항목, Q.학번), 값(항목, Q.이름));

  const 파일들 = 항목
    .filter(function (ir) { return ir.getItem().getType() === FormApp.ItemType.FILE_UPLOAD; })
    .reduce(function (acc, ir) { return acc.concat(ir.getResponse() || []); }, []);
  if (파일들.length === 0) {
    throw new Error('올린 파일이 없다. 폼의 파일 업로드 질문을 확인한다');
  }

  const 학생폴더 = 폴더확보(주차명, 폴더명);
  const 시각 = Utilities.formatDate(응답.getTimestamp(), TZ, 'yyyyMMdd-HHmm');

  const 옮긴것 = [];
  파일들.forEach(function (id) {
    const f = DriveApp.getFileById(id);
    if (제자리인가(f, 학생폴더)) return;
    if (!/^\d{8}-\d{4}_/.test(f.getName())) f.setName(시각 + '_' + f.getName());
    f.moveTo(학생폴더);
    옮긴것.push(f.getName());
  });

  return { 주차: 주차명, 학생: 폴더명, 옮긴것: 옮긴것, 전체: 파일들.length };
}

// ── 도우미 ──────────────────────────────────────────────────────────

/** 제목으로 답을 찾는다. 없으면 던진다 — 조용히 빈 폴더를 만들지 않기 위해서다. */
function 값(항목, 제목) {
  const 찾은것 = 항목.filter(function (ir) { return ir.getItem().getTitle().trim() === 제목; });
  if (찾은것.length === 0) {
    throw new Error('폼에 「' + 제목 + '」 질문이 없다. 제목을 바꿨는지 확인한다');
  }
  const v = String(찾은것[0].getResponse() || '').trim();
  if (!v) throw new Error('「' + 제목 + '」 이 비어 있다. 폼에서 필수로 두었는지 확인한다');
  return v;
}

/** 드롭다운 답이 설정의 주차목록에 있는 값인지 본다. 없으면 폴더를 만들지 않는다. */
function 주차확인(v) {
  const s = String(v).trim();
  if (주차목록.indexOf(s) < 0) {
    throw new Error('주차목록에 없는 값이다: 「' + s + '」. ' +
      '설정.gs 의 주차목록과 폼의 드롭다운이 어긋났는지 본다 (주차항목갱신())');
  }
  return s;
}

/** 학번_이름. 공백을 없애고 드라이브가 싫어하는 글자를 바꾼다. */
function 폴더이름(학번, 이름) {
  const 학 = 학번.replace(/\s+/g, '');
  const 명 = 이름.replace(/\s+/g, '');
  return (학 + '_' + 명).replace(/[\/\\:*?"<>|]/g, '-');
}

/** 설정.gs 를 아직 안 채운 자리인가. 구글이 뱉는 「No item with the given ID」를 미리 막는다. */
function 자리표시자(v) {
  return !v || String(v).indexOf('여기에') === 0;
}

function 제자리인가(파일, 폴더) {
  const it = 파일.getParents();
  while (it.hasNext()) {
    if (it.next().getId() === 폴더.getId()) return true;
  }
  return false;
}

/**
 * 루트 → 주차 → 학생 순으로 폴더를 얻는다. 없으면 만든다.
 *
 * 두 학생이 같은 순간에 내면 이름이 같은 폴더가 둘 생긴다.
 * 만드는 구간만 잠가 막는다.
 */
function 폴더확보(주차명, 학생폴더명) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const 루트 = DriveApp.getFolderById(ROOT_FOLDER_ID);
    return 하위폴더(하위폴더(루트, 주차명), 학생폴더명);
  } finally {
    lock.releaseLock();
  }
}

function 하위폴더(부모, 이름) {
  const it = 부모.getFoldersByName(이름);
  return it.hasNext() ? it.next() : 부모.createFolder(이름);
}

/** 기록 시트에 한 줄 붙인다. 없으면 루트에 만든다. */
function 기록(줄) {
  try {
    const props = PropertiesService.getScriptProperties();
    const id = props.getProperty('LOG_SHEET_ID');
    let ss;
    if (id) {
      ss = SpreadsheetApp.openById(id);
    } else {
      ss = SpreadsheetApp.create('과제수집-기록');
      DriveApp.getFileById(ss.getId()).moveTo(DriveApp.getFolderById(ROOT_FOLDER_ID));
      ss.getSheets()[0].appendRow(
        ['시각', '결과', '주차', '학생', '파일 수', '파일 이름', '오류']);
      props.setProperty('LOG_SHEET_ID', ss.getId());
    }
    ss.getSheets()[0].appendRow([new Date()].concat(줄));
  } catch (err) {
    // 기록에 실패해도 제출 처리는 계속한다.
    console.error('기록 실패: ' + err);
  }
}

function 알림(제목, 본문) {
  try {
    const to = 알림받을주소 || Session.getEffectiveUser().getEmail();
    MailApp.sendEmail(to, 제목, 본문);
  } catch (err) {
    console.error('알림 실패: ' + err);
  }
}
