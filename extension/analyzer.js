/*
  Phish Radar AI-Lite Analyzer v1.2
  ------------------------------------------------------------
  Demo-only URL + DOM risk scoring engine. It DOES NOT call external APIs
  and DOES NOT use a trained ML model. The goal is to demonstrate a clear,
  explainable phishing detection pipeline for a seminar/project prototype.
*/
(function (global) {
  'use strict';

  const BRAND_PROFILES = [
    { brand: 'google', aliases: ['gmail', 'youtube'], officialDomains: ['google.com', 'gmail.com', 'youtube.com', 'accounts.google.com', 'mail.google.com'] },
    { brand: 'facebook', aliases: ['fb', 'meta'], officialDomains: ['facebook.com', 'fb.com', 'meta.com', 'meta.ai', 'messenger.com'] },
    { brand: 'instagram', aliases: ['ig'], officialDomains: ['instagram.com'] },
    { brand: 'tiktok', aliases: ['tik tok'], officialDomains: ['tiktok.com'] },
    { brand: 'medium', aliases: [], officialDomains: ['medium.com'] },
    { brand: 'twitter', aliases: [], officialDomains: ['x.com', 'twitter.com'] },
    { brand: 'line', aliases: ['line'], officialDomains: ['line.me', 'linecorp.com', 'today.line.me'] },
    { brand: 'paypal', aliases: ['pay pal'], officialDomains: ['paypal.com', 'paypal.me'] },
    { brand: 'apple', aliases: ['icloud'], officialDomains: ['apple.com', 'icloud.com'] },
    { brand: 'microsoft', aliases: ['office', 'outlook', 'onedrive'], officialDomains: ['microsoft.com', 'live.com', 'outlook.com', 'office.com', 'office365.com', 'microsoftonline.com', 'login.microsoftonline.com'] },
    { brand: 'amazon', aliases: ['aws'], officialDomains: ['amazon.com', 'amazon.co.th', 'amazonaws.com', 'aws.amazon.com'] },
    { brand: 'netflix', aliases: [], officialDomains: ['netflix.com'] },
    { brand: 'steam', aliases: ['steampowered'], officialDomains: ['steampowered.com', 'steamcommunity.com'] },
    { brand: 'discord', aliases: [], officialDomains: ['discord.com', 'discord.gg'] },
    { brand: 'binance', aliases: [], officialDomains: ['binance.com'] },
    { brand: 'kbank', aliases: ['kasikorn', 'kasikornbank'], officialDomains: ['kbank.co.th', 'kasikornbank.com'] },
    { brand: 'scb', aliases: ['scbeasy', 'siamcommercial'], officialDomains: ['scb.co.th', 'scbeasy.com'] },
    { brand: 'krungsri', aliases: ['bay'], officialDomains: ['krungsri.com', 'bankofayudhya.com'] },
    { brand: 'ttb', aliases: ['tmb', 'thanachart'], officialDomains: ['ttbbank.com', 'ttb.co.th'] },
    { brand: 'krungthai', aliases: ['ktb'], officialDomains: ['krungthai.com', 'ktb.co.th'] },
    { brand: 'truemoney', aliases: ['truewallet', 'wallet'], officialDomains: ['truemoney.com', 'truemoney.co.th'] },
    { brand: 'promptpay', aliases: [], officialDomains: ['promptpay.io'] },
    { brand: 'shopee', aliases: ['shopeepay'], officialDomains: ['shopee.co.th', 'shopee.com', 'shopeepay.co.th'] },
    { brand: 'lazada', aliases: [], officialDomains: ['lazada.co.th', 'lazada.com'] }
  ];

  const KNOWN_BRANDS = BRAND_PROFILES.flatMap(p => [p.brand, ...p.aliases]).filter(Boolean);

  function keywordMatches(text, keywords) {
    // Match whole Latin terms, not pin in shopping or auth in author.
    // Case variants (otp / OTP) are one piece of evidence, not two.
    return [...new Set(keywords.map(k => k.toLowerCase()))].filter(keyword => {
      if (!/^[a-z0-9-]+$/.test(keyword)) return text.includes(keyword);
      return new RegExp('(?:^|[^a-z0-9])' + keyword + '(?=$|[^a-z0-9])').test(text);
    });
  }

  const SUSPICIOUS_KEYWORDS = [
    'login', 'signin', 'sign-in', 'verify', 'verification', 'secure', 'security',
    'account', 'update', 'confirm', 'unlock', 'wallet', 'banking', 'payment',
    'billing', 'support', 'helpdesk', 'password', 'passwd', 'otp', '2fa', 'mfa',
    'reset', 'limited', 'suspend', 'suspended', 'locked', 'gift', 'bonus', 'claim',
    'airdrop', 'free', 'urgent', 'reward', 'prize', 'refund', 'invoice', 'kyc',
    'validate', 'restore', 'appeal', 'risk', 'safe', 'protect', 'admin', 'webscr',
    'auth', 'authentication', 'session', 'token', 'seed', 'phrase', 'privatekey',
    'ยืนยัน', 'บัญชี', 'รหัสผ่าน', 'โอนเงิน', 'รับเงิน', 'ด่วน', 'ล็อกอิน', 'OTP'
  ];

  const CREDENTIAL_KEYWORDS = [
    'password', 'passwd', 'otp', '2fa', 'mfa', 'token', 'credential', 'seed',
    'recovery-phrase', 'privatekey', 'private-key', 'session', 'auth', 'pin',
    'รหัสผ่าน', 'รหัส', 'otp', 'โค้ด', 'seed phrase'
  ];

  const PRESSURE_WORDS = [
    'urgent', 'immediately', 'within 24 hours', 'suspended', 'locked',
    'verify your account', 'your account will be closed', 'limited time',
    'unusual activity', 'security alert', 'final warning', 'ด่วน',
    'ภายใน 24 ชั่วโมง', 'บัญชีถูกระงับ', 'บัญชีถูกล็อก', 'ยืนยันบัญชี',
    'ระงับบัญชี', 'รับสิทธิ์', 'ของรางวัล', 'แจ้งเตือนความปลอดภัย'
  ];

  const TLD_RISK = new Set([
    'zip', 'mov', 'top', 'xyz', 'click', 'link', 'country', 'stream', 'gq', 'tk',
    'ml', 'cf', 'rest', 'monster', 'quest', 'work', 'cam', 'icu', 'cfd', 'cyou',
    'buzz', 'fit', 'kim', 'lol', 'mom', 'sbs', 'skin', 'surf', 'tokyo'
  ]);

  const SHORTENERS = [
    'bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'is.gd', 'cutt.ly', 'shorturl.at',
    'rebrand.ly', 'buff.ly', 'ow.ly', 's.id', 'lnkd.in', 'rb.gy', 'tiny.cc'
  ];

  const FREE_HOSTING_OR_DDNS = [
    'github.io', 'pages.dev', 'netlify.app', 'vercel.app', 'web.app', 'firebaseapp.com',
    'glitch.me', '000webhostapp.com', 'weebly.com', 'wixsite.com', 'blogspot.com',
    'duckdns.org', 'no-ip.org', 'ddns.net', 'hopto.org', 'serveo.net', 'ngrok-free.app'
  ];

  const SUSPICIOUS_FILE_EXTENSIONS = [
    '.exe', '.scr', '.bat', '.cmd', '.com', '.pif', '.vbs', '.js', '.jse', '.wsf',
    '.ps1', '.msi', '.apk', '.dmg', '.iso', '.img', '.jar', '.hta', '.lnk'
  ];

  const ARCHIVE_EXTENSIONS = ['.zip', '.rar', '.7z', '.tar', '.gz'];


  // Search-result context rules: not every adult/spam result is phishing, but
  // adult keywords appearing on unrelated .org/.edu/CMS upload/PDF results are a
  // common sign of SEO spam, compromised pages, or risky redirects.
  const ADULT_SEO_KEYWORDS = [
    'porn', 'porno', 'pornhub', 'xvideos', 'xnxx', 'xhamster', 'xxx', 'adult',
    'sex videos', 'sex video', '18+', '+18', 'viral', 'droba', 'seks', 'sexy',
    'หนังโป๊', 'คลิปหลุด', 'ผู้ใหญ่'
  ];

  const ADULT_CONTENT_DOMAINS = [
    'xvideos.com', 'xnxx.com', 'pornhub.com', 'xhamster.com', 'redtube.com', 'youporn.com'
  ];

  // v1.2: broader risky-content categories for seminar demo. These are NOT
  // content-moderation labels and do not prove a site is illegal; they are
  // explainable signals for "ควรระวังก่อนเปิด" beyond phishing only.
  const MALWARE_CONTENT_KEYWORDS = [
    'malware', 'virus', 'trojan', 'ransomware', 'spyware', 'keylogger', 'stealer',
    'crack', 'keygen', 'activator', 'serial key', 'license crack', 'patch.exe',
    'setup.exe', 'download player', 'video codec', 'flash update', 'chrome update',
    'browser update', 'driver update', 'mod apk', 'apk download', 'free download',
    'torrent', 'โปรแกรมแครก', 'ตัวเปิดใช้งาน', 'ไวรัส', 'มัลแวร์', 'โทรจัน',
    'แครก', 'ดาวน์โหลด apk', 'โหลดโปรแกรมฟรี'
  ];

  const SCAM_CONTENT_KEYWORDS = [
    'get rich', 'make money fast', 'guaranteed profit', 'risk free profit',
    'double your money', 'investment bonus', 'giveaway', 'airdrop', 'claim reward',
    'claim prize', 'free money', 'loan approved', 'quick loan', 'work from home income',
    'รายได้เสริม', 'รายได้ดี', 'รวยเร็ว', 'กำไรแน่นอน', 'รับประกันกำไร',
    'ลงทุนผลตอบแทนสูง', 'แจกเงินฟรี', 'กู้เงินด่วน', 'ปล่อยกู้', 'อนุมัติไว',
    'เครดิตฟรี', 'รับรางวัล', 'รับสิทธิ์ฟรี', 'งานออนไลน์', 'โอนเงินก่อน'
  ];

  const GAMBLING_CONTENT_KEYWORDS = [
    'casino', 'slots', 'slot game', 'betting', 'sportsbook', 'บาคาร่า', 'สล็อต',
    'พนัน', 'แทงบอล', 'หวยออนไลน์', 'คาสิโน', 'เว็บพนัน', 'เดิมพัน', 'ฝากถอน'
  ];

  const SENSITIVE_ADULT_CONTEXT_KEYWORDS = [
    ...ADULT_SEO_KEYWORDS, 'leak video', 'คลิปหลุด', '18 video', 'adult video'
  ];

  const CMS_UPLOAD_PATTERNS = [
    'wp-content', 'wpforms', 'wpcf7-files', '/tmp/', '/temp/', '/uploads/', '/files/', '/publication/', '/publicacao/'
  ];

  const IGNORE_BRAND_TOKEN_MATCH = new Set([
    'www', 'www2', 'www3', 'm', 'mobile', 'web', 'app', 'api', 'cdn', 'static',
    'img', 'assets', 'mail', 'email', 'login', 'signin', 'auth', 'account',
    'secure', 'security', 'support', 'help', 'service', 'shop', 'blog'
  ]);

  function normalizeUrl(input) {
    if (!input) return null;
    try {
      return new URL(input, (typeof location !== 'undefined' ? location.href : 'https://example.com'));
    } catch (e) {
      try { return new URL('https://' + input); } catch (_) { return null; }
    }
  }

  function safeDecode(str) {
    try { return decodeURIComponent(str); } catch (_) { return String(str || ''); }
  }

  // BEGIN GENERATED PSL: MPL-2.0, publicsuffix.org; scripts/build_suffix_snapshot.py
  const PUBLIC_SUFFIX_RULES = new Set("ac com.ac edu.ac gov.ac mil.ac net.ac org.ac ad ae ac.ae co.ae gov.ae mil.ae net.ae org.ae sch.ae aero airline.aero airport.aero accident-investigation.aero accident-prevention.aero aerobatic.aero aeroclub.aero aerodrome.aero agents.aero air-surveillance.aero air-traffic-control.aero aircraft.aero airtraffic.aero ambulance.aero association.aero author.aero ballooning.aero broker.aero caa.aero cargo.aero catering.aero certification.aero championship.aero charter.aero civilaviation.aero club.aero conference.aero consultant.aero consulting.aero control.aero council.aero crew.aero design.aero dgca.aero educator.aero emergency.aero engine.aero engineer.aero entertainment.aero equipment.aero exchange.aero express.aero federation.aero flight.aero freight.aero fuel.aero gliding.aero government.aero groundhandling.aero group.aero hanggliding.aero homebuilt.aero insurance.aero journal.aero journalist.aero leasing.aero logistics.aero magazine.aero maintenance.aero marketplace.aero media.aero microlight.aero modelling.aero navigation.aero parachuting.aero paragliding.aero passenger-association.aero pilot.aero press.aero production.aero recreation.aero repbody.aero res.aero research.aero rotorcraft.aero safety.aero scientist.aero services.aero show.aero skydiving.aero software.aero student.aero taxi.aero trader.aero trading.aero trainer.aero union.aero workinggroup.aero works.aero af com.af edu.af gov.af net.af org.af ag co.ag com.ag net.ag nom.ag org.ag ai com.ai net.ai off.ai org.ai al com.al edu.al gov.al mil.al net.al org.al am co.am com.am commune.am net.am org.am ao co.ao ed.ao edu.ao gov.ao gv.ao it.ao og.ao org.ao pb.ao aq ar bet.ar com.ar coop.ar edu.ar gob.ar gov.ar int.ar mil.ar musica.ar mutual.ar net.ar org.ar senasa.ar tur.ar arpa e164.arpa home.arpa in-addr.arpa ip6.arpa iris.arpa uri.arpa urn.arpa as gov.as asia at ac.at sth.ac.at co.at gv.at or.at au asn.au com.au edu.au gov.au id.au net.au org.au conf.au oz.au act.au nsw.au nt.au qld.au sa.au tas.au vic.au wa.au act.edu.au catholic.edu.au nsw.edu.au nt.edu.au qld.edu.au sa.edu.au tas.edu.au vic.edu.au wa.edu.au qld.gov.au sa.gov.au tas.gov.au vic.gov.au wa.gov.au schools.nsw.edu.au aw com.aw ax az biz.az co.az com.az edu.az gov.az info.az int.az mil.az name.az net.az org.az pp.az pro.az ba com.ba edu.ba gov.ba mil.ba net.ba org.ba bb biz.bb co.bb com.bb edu.bb gov.bb info.bb net.bb org.bb store.bb tv.bb *.bd be ac.be bf gov.bf bg 0.bg 1.bg 2.bg 3.bg 4.bg 5.bg 6.bg 7.bg 8.bg 9.bg a.bg b.bg c.bg d.bg e.bg f.bg g.bg h.bg i.bg j.bg k.bg l.bg m.bg n.bg o.bg p.bg q.bg r.bg s.bg t.bg u.bg v.bg w.bg x.bg y.bg z.bg bh com.bh edu.bh gov.bh net.bh org.bh bi co.bi com.bi edu.bi or.bi org.bi biz bj africa.bj agro.bj architectes.bj assur.bj avocats.bj co.bj com.bj eco.bj econo.bj edu.bj info.bj loisirs.bj money.bj net.bj org.bj ote.bj restaurant.bj resto.bj tourism.bj univ.bj bm com.bm edu.bm gov.bm net.bm org.bm bn com.bn edu.bn gov.bn net.bn org.bn bo com.bo edu.bo gob.bo int.bo mil.bo net.bo org.bo tv.bo web.bo academia.bo agro.bo arte.bo blog.bo bolivia.bo ciencia.bo cooperativa.bo democracia.bo deporte.bo ecologia.bo economia.bo empresa.bo indigena.bo industria.bo info.bo medicina.bo movimiento.bo musica.bo natural.bo nombre.bo noticias.bo patria.bo plurinacional.bo politica.bo profesional.bo pueblo.bo revista.bo salud.bo tecnologia.bo tksat.bo transporte.bo wiki.bo br 9guacu.br abc.br adm.br adv.br agr.br aju.br am.br anani.br aparecida.br app.br arq.br art.br ato.br b.br barueri.br belem.br bet.br bhz.br bib.br bio.br blog.br bmd.br boavista.br bsb.br campinagrande.br campinas.br caxias.br cim.br cng.br cnt.br com.br contagem.br coop.br coz.br cri.br cuiaba.br curitiba.br def.br des.br det.br dev.br ecn.br eco.br edu.br emp.br enf.br eng.br esp.br etc.br eti.br far.br feira.br flog.br floripa.br fm.br fnd.br fortal.br fot.br foz.br fst.br g12.br geo.br ggf.br goiania.br gov.br ac.gov.br al.gov.br am.gov.br ap.gov.br ba.gov.br ce.gov.br df.gov.br es.gov.br go.gov.br ma.gov.br mg.gov.br ms.gov.br mt.gov.br pa.gov.br pb.gov.br pe.gov.br pi.gov.br pr.gov.br rj.gov.br rn.gov.br ro.gov.br rr.gov.br rs.gov.br sc.gov.br se.gov.br sp.gov.br to.gov.br gru.br imb.br ind.br inf.br jab.br jampa.br jdf.br joinville.br jor.br jus.br leg.br leilao.br lel.br log.br londrina.br macapa.br maceio.br manaus.br maringa.br mat.br med.br mil.br morena.br mp.br mus.br natal.br net.br niteroi.br *.nom.br not.br ntr.br odo.br ong.br org.br osasco.br palmas.br poa.br ppg.br pro.br psc.br psi.br pvh.br qsl.br radio.br rec.br recife.br rep.br ribeirao.br rio.br riobranco.br riopreto.br salvador.br sampa.br santamaria.br santoandre.br saobernardo.br saogonca.br seg.br sjc.br slg.br slz.br sorocaba.br srv.br taxi.br tc.br tec.br teo.br the.br tmp.br trd.br tur.br tv.br udi.br vet.br vix.br vlog.br wiki.br zlg.br bs com.bs edu.bs gov.bs net.bs org.bs bt com.bt edu.bt gov.bt net.bt org.bt bv bw ac.bw co.bw gov.bw net.bw org.bw by gov.by mil.by com.by of.by bz co.bz com.bz edu.bz gov.bz net.bz org.bz ca ab.ca bc.ca mb.ca nb.ca nf.ca nl.ca ns.ca nt.ca nu.ca on.ca pe.ca qc.ca sk.ca yk.ca gc.ca cat cc cd gov.cd cf cg ch ci ac.ci xn--aroport-bya.ci asso.ci co.ci com.ci ed.ci edu.ci go.ci gouv.ci int.ci net.ci or.ci org.ci *.ck !www.ck cl co.cl gob.cl gov.cl mil.cl cm co.cm com.cm gov.cm net.cm cn ac.cn com.cn edu.cn gov.cn mil.cn net.cn org.cn xn--55qx5d.cn xn--od0alg.cn xn--io0a7i.cn ah.cn bj.cn cq.cn fj.cn gd.cn gs.cn gx.cn gz.cn ha.cn hb.cn he.cn hi.cn hk.cn hl.cn hn.cn jl.cn js.cn jx.cn ln.cn mo.cn nm.cn nx.cn qh.cn sc.cn sd.cn sh.cn sn.cn sx.cn tj.cn tw.cn xj.cn xz.cn yn.cn zj.cn co com.co edu.co gov.co mil.co net.co nom.co org.co com coop cr ac.cr co.cr ed.cr fi.cr go.cr or.cr sa.cr cu com.cu edu.cu gob.cu inf.cu nat.cu net.cu org.cu cv com.cv edu.cv id.cv int.cv net.cv nome.cv org.cv publ.cv cw com.cw edu.cw net.cw org.cw cx gov.cx cy ac.cy biz.cy com.cy ekloges.cy gov.cy ltd.cy mil.cy net.cy org.cy press.cy pro.cy tm.cy cz de dj dk dm co.dm com.dm edu.dm gov.dm net.dm org.dm do art.do com.do edu.do gob.do gov.do mil.do net.do org.do sld.do web.do dz art.dz asso.dz com.dz edu.dz gov.dz net.dz org.dz pol.dz soc.dz tm.dz ec com.ec edu.ec fin.ec gob.ec gov.ec info.ec k12.ec med.ec mil.ec net.ec org.ec pro.ec edu ee aip.ee com.ee edu.ee fie.ee gov.ee lib.ee med.ee org.ee pri.ee riik.ee eg ac.eg com.eg edu.eg eun.eg gov.eg info.eg me.eg mil.eg name.eg net.eg org.eg sci.eg sport.eg tv.eg *.er es com.es edu.es gob.es nom.es org.es et biz.et com.et edu.et gov.et info.et name.et net.et org.et eu fi aland.fi fj ac.fj biz.fj com.fj gov.fj info.fj mil.fj name.fj net.fj org.fj pro.fj *.fk fm com.fm edu.fm net.fm org.fm fo fr asso.fr com.fr gouv.fr nom.fr prd.fr tm.fr avoues.fr cci.fr greta.fr huissier-justice.fr ga gb gd edu.gd gov.gd ge com.ge edu.ge gov.ge net.ge org.ge pvt.ge school.ge gf gg co.gg net.gg org.gg gh com.gh edu.gh gov.gh mil.gh org.gh gi com.gi edu.gi gov.gi ltd.gi mod.gi org.gi gl co.gl com.gl edu.gl net.gl org.gl gm gn ac.gn com.gn edu.gn gov.gn net.gn org.gn gov gp asso.gp com.gp edu.gp mobi.gp net.gp org.gp gq gr com.gr edu.gr gov.gr net.gr org.gr gs gt com.gt edu.gt gob.gt ind.gt mil.gt net.gt org.gt gu com.gu edu.gu gov.gu guam.gu info.gu net.gu org.gu web.gu gw gy co.gy com.gy edu.gy gov.gy net.gy org.gy hk com.hk edu.hk gov.hk idv.hk net.hk org.hk xn--ciqpn.hk xn--gmqw5a.hk xn--55qx5d.hk xn--mxtq1m.hk xn--lcvr32d.hk xn--wcvs22d.hk xn--gmq050i.hk xn--uc0atv.hk xn--uc0ay4a.hk xn--od0alg.hk xn--zf0avx.hk xn--mk0axi.hk xn--tn0ag.hk xn--od0aq3b.hk xn--io0a7i.hk hm hn com.hn edu.hn gob.hn mil.hn net.hn org.hn hr com.hr from.hr iz.hr name.hr ht adult.ht art.ht asso.ht com.ht coop.ht edu.ht firm.ht gouv.ht info.ht med.ht net.ht org.ht perso.ht pol.ht pro.ht rel.ht shop.ht hu 2000.hu agrar.hu bolt.hu casino.hu city.hu co.hu erotica.hu erotika.hu film.hu forum.hu games.hu hotel.hu info.hu ingatlan.hu jogasz.hu konyvelo.hu lakas.hu media.hu news.hu org.hu priv.hu reklam.hu sex.hu shop.hu sport.hu suli.hu szex.hu tm.hu tozsde.hu utazas.hu video.hu id ac.id biz.id co.id desa.id go.id mil.id my.id net.id or.id ponpes.id sch.id web.id ie gov.ie il ac.il co.il gov.il idf.il k12.il muni.il net.il org.il xn--4dbrk0ce xn--4dbgdty6c.xn--4dbrk0ce xn--5dbhl8d.xn--4dbrk0ce xn--8dbq2a.xn--4dbrk0ce xn--hebda8b.xn--4dbrk0ce im ac.im co.im ltd.co.im plc.co.im com.im net.im org.im tt.im tv.im in 5g.in 6g.in ac.in ai.in am.in bihar.in biz.in business.in ca.in cn.in co.in com.in coop.in cs.in delhi.in dr.in edu.in er.in firm.in gen.in gov.in gujarat.in ind.in info.in int.in internet.in io.in me.in mil.in net.in nic.in org.in pg.in post.in pro.in res.in travel.in tv.in uk.in up.in us.in info int eu.int io co.io com.io edu.io gov.io mil.io net.io nom.io org.io iq com.iq edu.iq gov.iq mil.iq net.iq org.iq ir ac.ir co.ir gov.ir id.ir net.ir org.ir sch.ir xn--mgba3a4f16a.ir xn--mgba3a4fra.ir is it edu.it gov.it abr.it abruzzo.it aosta-valley.it aostavalley.it bas.it basilicata.it cal.it calabria.it cam.it campania.it emilia-romagna.it emiliaromagna.it emr.it friuli-v-giulia.it friuli-ve-giulia.it friuli-vegiulia.it friuli-venezia-giulia.it friuli-veneziagiulia.it friuli-vgiulia.it friuliv-giulia.it friulive-giulia.it friulivegiulia.it friulivenezia-giulia.it friuliveneziagiulia.it friulivgiulia.it fvg.it laz.it lazio.it lig.it liguria.it lom.it lombardia.it lombardy.it lucania.it mar.it marche.it mol.it molise.it piedmont.it piemonte.it pmn.it pug.it puglia.it sar.it sardegna.it sardinia.it sic.it sicilia.it sicily.it taa.it tos.it toscana.it trentin-sud-tirol.it xn--trentin-sd-tirol-rzb.it trentin-sudtirol.it xn--trentin-sdtirol-7vb.it trentin-sued-tirol.it trentin-suedtirol.it trentino.it trentino-a-adige.it trentino-aadige.it trentino-alto-adige.it trentino-altoadige.it trentino-s-tirol.it trentino-stirol.it trentino-sud-tirol.it xn--trentino-sd-tirol-c3b.it trentino-sudtirol.it xn--trentino-sdtirol-szb.it trentino-sued-tirol.it trentino-suedtirol.it trentinoa-adige.it trentinoaadige.it trentinoalto-adige.it trentinoaltoadige.it trentinos-tirol.it trentinostirol.it trentinosud-tirol.it xn--trentinosd-tirol-rzb.it trentinosudtirol.it xn--trentinosdtirol-7vb.it trentinosued-tirol.it trentinosuedtirol.it trentinsud-tirol.it xn--trentinsd-tirol-6vb.it trentinsudtirol.it xn--trentinsdtirol-nsb.it trentinsued-tirol.it trentinsuedtirol.it tuscany.it umb.it umbria.it val-d-aosta.it val-daosta.it vald-aosta.it valdaosta.it valle-aosta.it valle-d-aosta.it valle-daosta.it valleaosta.it valled-aosta.it valledaosta.it vallee-aoste.it xn--valle-aoste-ebb.it vallee-d-aoste.it xn--valle-d-aoste-ehb.it valleeaoste.it xn--valleaoste-e7a.it valleedaoste.it xn--valledaoste-ebb.it vao.it vda.it ven.it veneto.it ag.it agrigento.it al.it alessandria.it alto-adige.it altoadige.it an.it ancona.it andria-barletta-trani.it andria-trani-barletta.it andriabarlettatrani.it andriatranibarletta.it ao.it aosta.it aoste.it ap.it aq.it aquila.it ar.it arezzo.it ascoli-piceno.it ascolipiceno.it asti.it at.it av.it avellino.it ba.it balsan.it balsan-sudtirol.it xn--balsan-sdtirol-nsb.it balsan-suedtirol.it bari.it barletta-trani-andria.it barlettatraniandria.it belluno.it benevento.it bergamo.it bg.it bi.it biella.it bl.it bn.it bo.it bologna.it bolzano.it bolzano-altoadige.it bozen.it bozen-sudtirol.it xn--bozen-sdtirol-2ob.it bozen-suedtirol.it br.it brescia.it brindisi.it bs.it bt.it bulsan.it bulsan-sudtirol.it xn--bulsan-sdtirol-nsb.it bulsan-suedtirol.it bz.it ca.it cagliari.it caltanissetta.it campidano-medio.it campidanomedio.it campobasso.it carbonia-iglesias.it carboniaiglesias.it carrara-massa.it carraramassa.it caserta.it catania.it catanzaro.it cb.it ce.it cesena-forli.it xn--cesena-forl-mcb.it cesenaforli.it xn--cesenaforl-i8a.it ch.it chieti.it ci.it cl.it cn.it co.it como.it cosenza.it cr.it cremona.it crotone.it cs.it ct.it cuneo.it cz.it dell-ogliastra.it dellogliastra.it en.it enna.it fc.it fe.it fermo.it ferrara.it fg.it fi.it firenze.it florence.it fm.it foggia.it forli-cesena.it xn--forl-cesena-fcb.it forlicesena.it xn--forlcesena-c8a.it fr.it frosinone.it ge.it genoa.it genova.it go.it gorizia.it gr.it grosseto.it iglesias-carbonia.it iglesiascarbonia.it im.it imperia.it is.it isernia.it kr.it la-spezia.it laquila.it laspezia.it latina.it lc.it le.it lecce.it lecco.it li.it livorno.it lo.it lodi.it lt.it lu.it lucca.it macerata.it mantova.it massa-carrara.it massacarrara.it matera.it mb.it mc.it me.it medio-campidano.it mediocampidano.it messina.it mi.it milan.it milano.it mn.it mo.it modena.it monza.it monza-brianza.it monza-e-della-brianza.it monzabrianza.it monzaebrianza.it monzaedellabrianza.it ms.it mt.it na.it naples.it napoli.it no.it novara.it nu.it nuoro.it og.it ogliastra.it olbia-tempio.it olbiatempio.it or.it oristano.it ot.it pa.it padova.it padua.it palermo.it parma.it pavia.it pc.it pd.it pe.it perugia.it pesaro-urbino.it pesarourbino.it pescara.it pg.it pi.it piacenza.it pisa.it pistoia.it pn.it po.it pordenone.it potenza.it pr.it prato.it pt.it pu.it pv.it pz.it ra.it ragusa.it ravenna.it rc.it re.it reggio-calabria.it reggio-emilia.it reggiocalabria.it reggioemilia.it rg.it ri.it rieti.it rimini.it rm.it rn.it ro.it roma.it rome.it rovigo.it sa.it salerno.it sassari.it savona.it si.it siena.it siracusa.it so.it sondrio.it sp.it sr.it ss.it xn--sdtirol-n2a.it suedtirol.it sv.it ta.it taranto.it te.it tempio-olbia.it tempioolbia.it teramo.it terni.it tn.it to.it torino.it tp.it tr.it trani-andria-barletta.it trani-barletta-andria.it traniandriabarletta.it tranibarlettaandria.it trapani.it trento.it treviso.it trieste.it ts.it turin.it tv.it ud.it udine.it urbino-pesaro.it urbinopesaro.it va.it varese.it vb.it vc.it ve.it venezia.it venice.it verbania.it vercelli.it verona.it vi.it vibo-valentia.it vibovalentia.it vicenza.it viterbo.it vr.it vs.it vt.it vv.it je co.je net.je org.je *.jm jo agri.jo ai.jo com.jo edu.jo eng.jo fm.jo gov.jo mil.jo net.jo org.jo per.jo phd.jo sch.jo tv.jo jobs jp ac.jp ad.jp co.jp ed.jp go.jp gr.jp lg.jp ne.jp or.jp aichi.jp akita.jp aomori.jp chiba.jp ehime.jp fukui.jp fukuoka.jp fukushima.jp gifu.jp gunma.jp hiroshima.jp hokkaido.jp hyogo.jp ibaraki.jp ishikawa.jp iwate.jp kagawa.jp kagoshima.jp kanagawa.jp kochi.jp kumamoto.jp kyoto.jp mie.jp miyagi.jp miyazaki.jp nagano.jp nagasaki.jp nara.jp niigata.jp oita.jp okayama.jp okinawa.jp osaka.jp saga.jp saitama.jp shiga.jp shimane.jp shizuoka.jp tochigi.jp tokushima.jp tokyo.jp tottori.jp toyama.jp wakayama.jp yamagata.jp yamaguchi.jp yamanashi.jp xn--ehqz56n.jp xn--1lqs03n.jp xn--qqqt11m.jp xn--f6qx53a.jp xn--djrs72d6uy.jp xn--mkru45i.jp xn--0trq7p7nn.jp xn--5js045d.jp xn--kbrq7o.jp xn--pssu33l.jp xn--ntsq17g.jp xn--uisz3g.jp xn--6btw5a.jp xn--1ctwo.jp xn--6orx2r.jp xn--rht61e.jp xn--rht27z.jp xn--nit225k.jp xn--rht3d.jp xn--djty4k.jp xn--klty5x.jp xn--kltx9a.jp xn--kltp7d.jp xn--c3s14m.jp xn--vgu402c.jp xn--efvn9s.jp xn--1lqs71d.jp xn--4pvxs.jp xn--uuwu58a.jp xn--zbx025d.jp xn--8pvr4u.jp xn--5rtp49c.jp xn--ntso0iqx3a.jp xn--elqq16h.jp xn--4it168d.jp xn--klt787d.jp xn--rny31h.jp xn--7t0a264c.jp xn--uist22h.jp xn--8ltr62k.jp xn--2m4a15e.jp xn--32vp30h.jp xn--4it797k.jp xn--5rtq34k.jp xn--k7yn95e.jp xn--tor131o.jp xn--d5qv7z876c.jp *.kawasaki.jp !city.kawasaki.jp *.kitakyushu.jp !city.kitakyushu.jp *.kobe.jp !city.kobe.jp *.nagoya.jp !city.nagoya.jp *.sapporo.jp !city.sapporo.jp *.sendai.jp !city.sendai.jp *.yokohama.jp !city.yokohama.jp aisai.aichi.jp ama.aichi.jp anjo.aichi.jp asuke.aichi.jp chiryu.aichi.jp chita.aichi.jp fuso.aichi.jp gamagori.aichi.jp handa.aichi.jp hazu.aichi.jp hekinan.aichi.jp higashiura.aichi.jp ichinomiya.aichi.jp inazawa.aichi.jp inuyama.aichi.jp isshiki.aichi.jp iwakura.aichi.jp kanie.aichi.jp kariya.aichi.jp kasugai.aichi.jp kira.aichi.jp kiyosu.aichi.jp komaki.aichi.jp konan.aichi.jp kota.aichi.jp mihama.aichi.jp miyoshi.aichi.jp nishio.aichi.jp nisshin.aichi.jp obu.aichi.jp oguchi.aichi.jp oharu.aichi.jp okazaki.aichi.jp owariasahi.aichi.jp seto.aichi.jp shikatsu.aichi.jp shinshiro.aichi.jp shitara.aichi.jp tahara.aichi.jp takahama.aichi.jp tobishima.aichi.jp toei.aichi.jp togo.aichi.jp tokai.aichi.jp tokoname.aichi.jp toyoake.aichi.jp toyohashi.aichi.jp toyokawa.aichi.jp toyone.aichi.jp toyota.aichi.jp tsushima.aichi.jp yatomi.aichi.jp akita.akita.jp daisen.akita.jp fujisato.akita.jp gojome.akita.jp hachirogata.akita.jp happou.akita.jp higashinaruse.akita.jp honjo.akita.jp honjyo.akita.jp ikawa.akita.jp kamikoani.akita.jp kamioka.akita.jp katagami.akita.jp kazuno.akita.jp kitaakita.akita.jp kosaka.akita.jp kyowa.akita.jp misato.akita.jp mitane.akita.jp moriyoshi.akita.jp nikaho.akita.jp noshiro.akita.jp odate.akita.jp oga.akita.jp ogata.akita.jp semboku.akita.jp yokote.akita.jp yurihonjo.akita.jp aomori.aomori.jp gonohe.aomori.jp hachinohe.aomori.jp hashikami.aomori.jp hiranai.aomori.jp hirosaki.aomori.jp itayanagi.aomori.jp kuroishi.aomori.jp misawa.aomori.jp mutsu.aomori.jp nakadomari.aomori.jp noheji.aomori.jp oirase.aomori.jp owani.aomori.jp rokunohe.aomori.jp sannohe.aomori.jp shichinohe.aomori.jp shingo.aomori.jp takko.aomori.jp towada.aomori.jp tsugaru.aomori.jp tsuruta.aomori.jp abiko.chiba.jp asahi.chiba.jp chonan.chiba.jp chosei.chiba.jp choshi.chiba.jp chuo.chiba.jp funabashi.chiba.jp futtsu.chiba.jp hanamigawa.chiba.jp ichihara.chiba.jp ichikawa.chiba.jp ichinomiya.chiba.jp inzai.chiba.jp isumi.chiba.jp kamagaya.chiba.jp kamogawa.chiba.jp kashiwa.chiba.jp katori.chiba.jp katsuura.chiba.jp kimitsu.chiba.jp kisarazu.chiba.jp kozaki.chiba.jp kujukuri.chiba.jp kyonan.chiba.jp matsudo.chiba.jp midori.chiba.jp mihama.chiba.jp minamiboso.chiba.jp mobara.chiba.jp mutsuzawa.chiba.jp nagara.chiba.jp nagareyama.chiba.jp narashino.chiba.jp narita.chiba.jp noda.chiba.jp oamishirasato.chiba.jp omigawa.chiba.jp onjuku.chiba.jp otaki.chiba.jp sakae.chiba.jp sakura.chiba.jp shimofusa.chiba.jp shirako.chiba.jp shiroi.chiba.jp shisui.chiba.jp sodegaura.chiba.jp sosa.chiba.jp tako.chiba.jp tateyama.chiba.jp togane.chiba.jp tohnosho.chiba.jp tomisato.chiba.jp urayasu.chiba.jp yachimata.chiba.jp yachiyo.chiba.jp yokaichiba.chiba.jp yokoshibahikari.chiba.jp yotsukaido.chiba.jp ainan.ehime.jp honai.ehime.jp ikata.ehime.jp imabari.ehime.jp iyo.ehime.jp kamijima.ehime.jp kihoku.ehime.jp kumakogen.ehime.jp masaki.ehime.jp matsuno.ehime.jp matsuyama.ehime.jp namikata.ehime.jp niihama.ehime.jp ozu.ehime.jp saijo.ehime.jp seiyo.ehime.jp shikokuchuo.ehime.jp tobe.ehime.jp toon.ehime.jp uchiko.ehime.jp uwajima.ehime.jp yawatahama.ehime.jp echizen.fukui.jp eiheiji.fukui.jp fukui.fukui.jp ikeda.fukui.jp katsuyama.fukui.jp mihama.fukui.jp minamiechizen.fukui.jp obama.fukui.jp ohi.fukui.jp ono.fukui.jp sabae.fukui.jp sakai.fukui.jp takahama.fukui.jp tsuruga.fukui.jp wakasa.fukui.jp ashiya.fukuoka.jp buzen.fukuoka.jp chikugo.fukuoka.jp chikuho.fukuoka.jp chikujo.fukuoka.jp chikushino.fukuoka.jp chikuzen.fukuoka.jp chuo.fukuoka.jp dazaifu.fukuoka.jp fukuchi.fukuoka.jp hakata.fukuoka.jp higashi.fukuoka.jp hirokawa.fukuoka.jp hisayama.fukuoka.jp iizuka.fukuoka.jp inatsuki.fukuoka.jp kaho.fukuoka.jp kasuga.fukuoka.jp kasuya.fukuoka.jp kawara.fukuoka.jp keisen.fukuoka.jp koga.fukuoka.jp kurate.fukuoka.jp kurogi.fukuoka.jp kurume.fukuoka.jp minami.fukuoka.jp miyako.fukuoka.jp miyama.fukuoka.jp miyawaka.fukuoka.jp mizumaki.fukuoka.jp munakata.fukuoka.jp nakagawa.fukuoka.jp nakama.fukuoka.jp nishi.fukuoka.jp nogata.fukuoka.jp ogori.fukuoka.jp okagaki.fukuoka.jp okawa.fukuoka.jp oki.fukuoka.jp omuta.fukuoka.jp onga.fukuoka.jp onojo.fukuoka.jp oto.fukuoka.jp saigawa.fukuoka.jp sasaguri.fukuoka.jp shingu.fukuoka.jp shinyoshitomi.fukuoka.jp shonai.fukuoka.jp soeda.fukuoka.jp sue.fukuoka.jp tachiarai.fukuoka.jp tagawa.fukuoka.jp takata.fukuoka.jp toho.fukuoka.jp toyotsu.fukuoka.jp tsuiki.fukuoka.jp ukiha.fukuoka.jp umi.fukuoka.jp usui.fukuoka.jp yamada.fukuoka.jp yame.fukuoka.jp yanagawa.fukuoka.jp yukuhashi.fukuoka.jp aizubange.fukushima.jp aizumisato.fukushima.jp aizuwakamatsu.fukushima.jp asakawa.fukushima.jp bandai.fukushima.jp date.fukushima.jp fukushima.fukushima.jp furudono.fukushima.jp futaba.fukushima.jp hanawa.fukushima.jp higashi.fukushima.jp hirata.fukushima.jp hirono.fukushima.jp iitate.fukushima.jp inawashiro.fukushima.jp ishikawa.fukushima.jp iwaki.fukushima.jp izumizaki.fukushima.jp kagamiishi.fukushima.jp kaneyama.fukushima.jp kawamata.fukushima.jp kitakata.fukushima.jp kitashiobara.fukushima.jp koori.fukushima.jp koriyama.fukushima.jp kunimi.fukushima.jp miharu.fukushima.jp mishima.fukushima.jp namie.fukushima.jp nango.fukushima.jp nishiaizu.fukushima.jp nishigo.fukushima.jp okuma.fukushima.jp omotego.fukushima.jp ono.fukushima.jp otama.fukushima.jp samegawa.fukushima.jp shimogo.fukushima.jp shirakawa.fukushima.jp showa.fukushima.jp soma.fukushima.jp sukagawa.fukushima.jp taishin.fukushima.jp tamakawa.fukushima.jp tanagura.fukushima.jp tenei.fukushima.jp yabuki.fukushima.jp yamato.fukushima.jp yamatsuri.fukushima.jp yanaizu.fukushima.jp yugawa.fukushima.jp anpachi.gifu.jp ena.gifu.jp gifu.gifu.jp ginan.gifu.jp godo.gifu.jp gujo.gifu.jp hashima.gifu.jp hichiso.gifu.jp hida.gifu.jp higashishirakawa.gifu.jp ibigawa.gifu.jp ikeda.gifu.jp kakamigahara.gifu.jp kani.gifu.jp kasahara.gifu.jp kasamatsu.gifu.jp kawaue.gifu.jp kitagata.gifu.jp mino.gifu.jp minokamo.gifu.jp mitake.gifu.jp mizunami.gifu.jp motosu.gifu.jp nakatsugawa.gifu.jp ogaki.gifu.jp sakahogi.gifu.jp seki.gifu.jp sekigahara.gifu.jp shirakawa.gifu.jp tajimi.gifu.jp takayama.gifu.jp tarui.gifu.jp toki.gifu.jp tomika.gifu.jp wanouchi.gifu.jp yamagata.gifu.jp yaotsu.gifu.jp yoro.gifu.jp annaka.gunma.jp chiyoda.gunma.jp fujioka.gunma.jp higashiagatsuma.gunma.jp isesaki.gunma.jp itakura.gunma.jp kanna.gunma.jp kanra.gunma.jp katashina.gunma.jp kawaba.gunma.jp kiryu.gunma.jp kusatsu.gunma.jp maebashi.gunma.jp meiwa.gunma.jp midori.gunma.jp minakami.gunma.jp naganohara.gunma.jp nakanojo.gunma.jp nanmoku.gunma.jp numata.gunma.jp oizumi.gunma.jp ora.gunma.jp ota.gunma.jp shibukawa.gunma.jp shimonita.gunma.jp shinto.gunma.jp showa.gunma.jp takasaki.gunma.jp takayama.gunma.jp tamamura.gunma.jp tatebayashi.gunma.jp tomioka.gunma.jp tsukiyono.gunma.jp tsumagoi.gunma.jp ueno.gunma.jp yoshioka.gunma.jp asaminami.hiroshima.jp daiwa.hiroshima.jp etajima.hiroshima.jp fuchu.hiroshima.jp fukuyama.hiroshima.jp hatsukaichi.hiroshima.jp higashihiroshima.hiroshima.jp hongo.hiroshima.jp jinsekikogen.hiroshima.jp kaita.hiroshima.jp kui.hiroshima.jp kumano.hiroshima.jp kure.hiroshima.jp mihara.hiroshima.jp miyoshi.hiroshima.jp naka.hiroshima.jp onomichi.hiroshima.jp osakikamijima.hiroshima.jp otake.hiroshima.jp saka.hiroshima.jp sera.hiroshima.jp seranishi.hiroshima.jp shinichi.hiroshima.jp shobara.hiroshima.jp takehara.hiroshima.jp abashiri.hokkaido.jp abira.hokkaido.jp aibetsu.hokkaido.jp akabira.hokkaido.jp akkeshi.hokkaido.jp asahikawa.hokkaido.jp ashibetsu.hokkaido.jp ashoro.hokkaido.jp assabu.hokkaido.jp atsuma.hokkaido.jp bibai.hokkaido.jp biei.hokkaido.jp bifuka.hokkaido.jp bihoro.hokkaido.jp biratori.hokkaido.jp chippubetsu.hokkaido.jp chitose.hokkaido.jp date.hokkaido.jp ebetsu.hokkaido.jp embetsu.hokkaido.jp eniwa.hokkaido.jp erimo.hokkaido.jp esan.hokkaido.jp esashi.hokkaido.jp fukagawa.hokkaido.jp fukushima.hokkaido.jp furano.hokkaido.jp furubira.hokkaido.jp haboro.hokkaido.jp hakodate.hokkaido.jp hamatonbetsu.hokkaido.jp hidaka.hokkaido.jp higashikagura.hokkaido.jp higashikawa.hokkaido.jp hiroo.hokkaido.jp hokuryu.hokkaido.jp hokuto.hokkaido.jp honbetsu.hokkaido.jp horokanai.hokkaido.jp horonobe.hokkaido.jp ikeda.hokkaido.jp imakane.hokkaido.jp ishikari.hokkaido.jp iwamizawa.hokkaido.jp iwanai.hokkaido.jp kamifurano.hokkaido.jp kamikawa.hokkaido.jp kamishihoro.hokkaido.jp kamisunagawa.hokkaido.jp kamoenai.hokkaido.jp kayabe.hokkaido.jp kembuchi.hokkaido.jp kikonai.hokkaido.jp kimobetsu.hokkaido.jp kitahiroshima.hokkaido.jp kitami.hokkaido.jp kiyosato.hokkaido.jp koshimizu.hokkaido.jp kunneppu.hokkaido.jp kuriyama.hokkaido.jp kuromatsunai.hokkaido.jp kushiro.hokkaido.jp kutchan.hokkaido.jp kyowa.hokkaido.jp mashike.hokkaido.jp matsumae.hokkaido.jp mikasa.hokkaido.jp minamifurano.hokkaido.jp mombetsu.hokkaido.jp moseushi.hokkaido.jp mukawa.hokkaido.jp muroran.hokkaido.jp naie.hokkaido.jp nakagawa.hokkaido.jp nakasatsunai.hokkaido.jp nakatombetsu.hokkaido.jp nanae.hokkaido.jp nanporo.hokkaido.jp nayoro.hokkaido.jp nemuro.hokkaido.jp niikappu.hokkaido.jp niki.hokkaido.jp nishiokoppe.hokkaido.jp noboribetsu.hokkaido.jp numata.hokkaido.jp obihiro.hokkaido.jp obira.hokkaido.jp oketo.hokkaido.jp okoppe.hokkaido.jp otaru.hokkaido.jp otobe.hokkaido.jp otofuke.hokkaido.jp otoineppu.hokkaido.jp oumu.hokkaido.jp ozora.hokkaido.jp pippu.hokkaido.jp rankoshi.hokkaido.jp rebun.hokkaido.jp rikubetsu.hokkaido.jp rishiri.hokkaido.jp rishirifuji.hokkaido.jp saroma.hokkaido.jp sarufutsu.hokkaido.jp shakotan.hokkaido.jp shari.hokkaido.jp shibecha.hokkaido.jp shibetsu.hokkaido.jp shikabe.hokkaido.jp shikaoi.hokkaido.jp shimamaki.hokkaido.jp shimizu.hokkaido.jp shimokawa.hokkaido.jp shinshinotsu.hokkaido.jp shintoku.hokkaido.jp shiranuka.hokkaido.jp shiraoi.hokkaido.jp shiriuchi.hokkaido.jp sobetsu.hokkaido.jp sunagawa.hokkaido.jp taiki.hokkaido.jp takasu.hokkaido.jp takikawa.hokkaido.jp takinoue.hokkaido.jp teshikaga.hokkaido.jp tobetsu.hokkaido.jp tohma.hokkaido.jp tomakomai.hokkaido.jp tomari.hokkaido.jp toya.hokkaido.jp toyako.hokkaido.jp toyotomi.hokkaido.jp toyoura.hokkaido.jp tsubetsu.hokkaido.jp tsukigata.hokkaido.jp urakawa.hokkaido.jp urausu.hokkaido.jp uryu.hokkaido.jp utashinai.hokkaido.jp wakkanai.hokkaido.jp wassamu.hokkaido.jp yakumo.hokkaido.jp yoichi.hokkaido.jp aioi.hyogo.jp akashi.hyogo.jp ako.hyogo.jp amagasaki.hyogo.jp aogaki.hyogo.jp asago.hyogo.jp ashiya.hyogo.jp awaji.hyogo.jp fukusaki.hyogo.jp goshiki.hyogo.jp harima.hyogo.jp himeji.hyogo.jp ichikawa.hyogo.jp inagawa.hyogo.jp itami.hyogo.jp kakogawa.hyogo.jp kamigori.hyogo.jp kamikawa.hyogo.jp kasai.hyogo.jp kasuga.hyogo.jp kawanishi.hyogo.jp miki.hyogo.jp minamiawaji.hyogo.jp nishinomiya.hyogo.jp nishiwaki.hyogo.jp ono.hyogo.jp sanda.hyogo.jp sannan.hyogo.jp sasayama.hyogo.jp sayo.hyogo.jp shingu.hyogo.jp shinonsen.hyogo.jp shiso.hyogo.jp sumoto.hyogo.jp taishi.hyogo.jp taka.hyogo.jp takarazuka.hyogo.jp takasago.hyogo.jp takino.hyogo.jp tamba.hyogo.jp tatsuno.hyogo.jp toyooka.hyogo.jp yabu.hyogo.jp yashiro.hyogo.jp yoka.hyogo.jp yokawa.hyogo.jp ami.ibaraki.jp asahi.ibaraki.jp bando.ibaraki.jp chikusei.ibaraki.jp daigo.ibaraki.jp fujishiro.ibaraki.jp hitachi.ibaraki.jp hitachinaka.ibaraki.jp hitachiomiya.ibaraki.jp hitachiota.ibaraki.jp ibaraki.ibaraki.jp ina.ibaraki.jp inashiki.ibaraki.jp itako.ibaraki.jp iwama.ibaraki.jp joso.ibaraki.jp kamisu.ibaraki.jp kasama.ibaraki.jp kashima.ibaraki.jp kasumigaura.ibaraki.jp koga.ibaraki.jp miho.ibaraki.jp mito.ibaraki.jp moriya.ibaraki.jp naka.ibaraki.jp namegata.ibaraki.jp oarai.ibaraki.jp ogawa.ibaraki.jp omitama.ibaraki.jp ryugasaki.ibaraki.jp sakai.ibaraki.jp sakuragawa.ibaraki.jp shimodate.ibaraki.jp shimotsuma.ibaraki.jp shirosato.ibaraki.jp sowa.ibaraki.jp suifu.ibaraki.jp takahagi.ibaraki.jp tamatsukuri.ibaraki.jp tokai.ibaraki.jp tomobe.ibaraki.jp tone.ibaraki.jp toride.ibaraki.jp tsuchiura.ibaraki.jp tsukuba.ibaraki.jp uchihara.ibaraki.jp ushiku.ibaraki.jp yachiyo.ibaraki.jp yamagata.ibaraki.jp yawara.ibaraki.jp yuki.ibaraki.jp anamizu.ishikawa.jp hakui.ishikawa.jp hakusan.ishikawa.jp kaga.ishikawa.jp kahoku.ishikawa.jp kanazawa.ishikawa.jp kawakita.ishikawa.jp komatsu.ishikawa.jp nakanoto.ishikawa.jp nanao.ishikawa.jp nomi.ishikawa.jp nonoichi.ishikawa.jp noto.ishikawa.jp shika.ishikawa.jp suzu.ishikawa.jp tsubata.ishikawa.jp tsurugi.ishikawa.jp uchinada.ishikawa.jp wajima.ishikawa.jp fudai.iwate.jp fujisawa.iwate.jp hanamaki.iwate.jp hiraizumi.iwate.jp hirono.iwate.jp ichinohe.iwate.jp ichinoseki.iwate.jp iwaizumi.iwate.jp iwate.iwate.jp joboji.iwate.jp kamaishi.iwate.jp kanegasaki.iwate.jp karumai.iwate.jp kawai.iwate.jp kitakami.iwate.jp kuji.iwate.jp kunohe.iwate.jp kuzumaki.iwate.jp miyako.iwate.jp mizusawa.iwate.jp morioka.iwate.jp ninohe.iwate.jp noda.iwate.jp ofunato.iwate.jp oshu.iwate.jp otsuchi.iwate.jp rikuzentakata.iwate.jp shiwa.iwate.jp shizukuishi.iwate.jp sumita.iwate.jp tanohata.iwate.jp tono.iwate.jp yahaba.iwate.jp yamada.iwate.jp ayagawa.kagawa.jp higashikagawa.kagawa.jp kanonji.kagawa.jp kotohira.kagawa.jp manno.kagawa.jp marugame.kagawa.jp mitoyo.kagawa.jp naoshima.kagawa.jp sanuki.kagawa.jp tadotsu.kagawa.jp takamatsu.kagawa.jp tonosho.kagawa.jp uchinomi.kagawa.jp utazu.kagawa.jp zentsuji.kagawa.jp akune.kagoshima.jp amami.kagoshima.jp hioki.kagoshima.jp isa.kagoshima.jp isen.kagoshima.jp izumi.kagoshima.jp kagoshima.kagoshima.jp kanoya.kagoshima.jp kawanabe.kagoshima.jp kinko.kagoshima.jp kouyama.kagoshima.jp makurazaki.kagoshima.jp matsumoto.kagoshima.jp minamitane.kagoshima.jp nakatane.kagoshima.jp nishinoomote.kagoshima.jp satsumasendai.kagoshima.jp soo.kagoshima.jp tarumizu.kagoshima.jp yusui.kagoshima.jp aikawa.kanagawa.jp atsugi.kanagawa.jp ayase.kanagawa.jp chigasaki.kanagawa.jp ebina.kanagawa.jp fujisawa.kanagawa.jp hadano.kanagawa.jp hakone.kanagawa.jp hiratsuka.kanagawa.jp isehara.kanagawa.jp kaisei.kanagawa.jp kamakura.kanagawa.jp kiyokawa.kanagawa.jp matsuda.kanagawa.jp minamiashigara.kanagawa.jp miura.kanagawa.jp nakai.kanagawa.jp ninomiya.kanagawa.jp odawara.kanagawa.jp oi.kanagawa.jp oiso.kanagawa.jp sagamihara.kanagawa.jp samukawa.kanagawa.jp tsukui.kanagawa.jp yamakita.kanagawa.jp yamato.kanagawa.jp yokosuka.kanagawa.jp yugawara.kanagawa.jp zama.kanagawa.jp zushi.kanagawa.jp aki.kochi.jp geisei.kochi.jp hidaka.kochi.jp higashitsuno.kochi.jp ino.kochi.jp kagami.kochi.jp kami.kochi.jp kitagawa.kochi.jp kochi.kochi.jp mihara.kochi.jp motoyama.kochi.jp muroto.kochi.jp nahari.kochi.jp nakamura.kochi.jp nankoku.kochi.jp nishitosa.kochi.jp niyodogawa.kochi.jp ochi.kochi.jp okawa.kochi.jp otoyo.kochi.jp otsuki.kochi.jp sakawa.kochi.jp sukumo.kochi.jp susaki.kochi.jp tosa.kochi.jp tosashimizu.kochi.jp toyo.kochi.jp tsuno.kochi.jp umaji.kochi.jp yasuda.kochi.jp yusuhara.kochi.jp amakusa.kumamoto.jp arao.kumamoto.jp aso.kumamoto.jp choyo.kumamoto.jp gyokuto.kumamoto.jp kamiamakusa.kumamoto.jp kikuchi.kumamoto.jp kumamoto.kumamoto.jp mashiki.kumamoto.jp mifune.kumamoto.jp minamata.kumamoto.jp minamioguni.kumamoto.jp nagasu.kumamoto.jp nishihara.kumamoto.jp oguni.kumamoto.jp ozu.kumamoto.jp sumoto.kumamoto.jp takamori.kumamoto.jp uki.kumamoto.jp uto.kumamoto.jp yamaga.kumamoto.jp yamato.kumamoto.jp yatsushiro.kumamoto.jp ayabe.kyoto.jp fukuchiyama.kyoto.jp higashiyama.kyoto.jp ide.kyoto.jp ine.kyoto.jp joyo.kyoto.jp kameoka.kyoto.jp kamo.kyoto.jp kita.kyoto.jp kizu.kyoto.jp kumiyama.kyoto.jp kyotamba.kyoto.jp kyotanabe.kyoto.jp kyotango.kyoto.jp maizuru.kyoto.jp minami.kyoto.jp minamiyamashiro.kyoto.jp miyazu.kyoto.jp muko.kyoto.jp nagaokakyo.kyoto.jp nakagyo.kyoto.jp nantan.kyoto.jp oyamazaki.kyoto.jp sakyo.kyoto.jp seika.kyoto.jp tanabe.kyoto.jp uji.kyoto.jp ujitawara.kyoto.jp wazuka.kyoto.jp yamashina.kyoto.jp yawata.kyoto.jp asahi.mie.jp inabe.mie.jp ise.mie.jp kameyama.mie.jp kawagoe.mie.jp kiho.mie.jp kisosaki.mie.jp kiwa.mie.jp komono.mie.jp kumano.mie.jp kuwana.mie.jp matsusaka.mie.jp meiwa.mie.jp mihama.mie.jp minamiise.mie.jp misugi.mie.jp miyama.mie.jp nabari.mie.jp shima.mie.jp suzuka.mie.jp tado.mie.jp taiki.mie.jp taki.mie.jp tamaki.mie.jp toba.mie.jp tsu.mie.jp udono.mie.jp ureshino.mie.jp watarai.mie.jp yokkaichi.mie.jp furukawa.miyagi.jp higashimatsushima.miyagi.jp ishinomaki.miyagi.jp iwanuma.miyagi.jp kakuda.miyagi.jp kami.miyagi.jp kawasaki.miyagi.jp marumori.miyagi.jp matsushima.miyagi.jp minamisanriku.miyagi.jp misato.miyagi.jp murata.miyagi.jp natori.miyagi.jp ogawara.miyagi.jp ohira.miyagi.jp onagawa.miyagi.jp osaki.miyagi.jp rifu.miyagi.jp semine.miyagi.jp shibata.miyagi.jp shichikashuku.miyagi.jp shikama.miyagi.jp shiogama.miyagi.jp shiroishi.miyagi.jp tagajo.miyagi.jp taiwa.miyagi.jp tome.miyagi.jp tomiya.miyagi.jp wakuya.miyagi.jp watari.miyagi.jp yamamoto.miyagi.jp zao.miyagi.jp aya.miyazaki.jp ebino.miyazaki.jp gokase.miyazaki.jp hyuga.miyazaki.jp kadogawa.miyazaki.jp kawaminami.miyazaki.jp kijo.miyazaki.jp kitagawa.miyazaki.jp kitakata.miyazaki.jp kitaura.miyazaki.jp kobayashi.miyazaki.jp kunitomi.miyazaki.jp kushima.miyazaki.jp mimata.miyazaki.jp miyakonojo.miyazaki.jp miyazaki.miyazaki.jp morotsuka.miyazaki.jp nichinan.miyazaki.jp nishimera.miyazaki.jp nobeoka.miyazaki.jp saito.miyazaki.jp shiiba.miyazaki.jp shintomi.miyazaki.jp takaharu.miyazaki.jp takanabe.miyazaki.jp takazaki.miyazaki.jp tsuno.miyazaki.jp achi.nagano.jp agematsu.nagano.jp anan.nagano.jp aoki.nagano.jp asahi.nagano.jp azumino.nagano.jp chikuhoku.nagano.jp chikuma.nagano.jp chino.nagano.jp fujimi.nagano.jp hakuba.nagano.jp hara.nagano.jp hiraya.nagano.jp iida.nagano.jp iijima.nagano.jp iiyama.nagano.jp iizuna.nagano.jp ikeda.nagano.jp ikusaka.nagano.jp ina.nagano.jp karuizawa.nagano.jp kawakami.nagano.jp kiso.nagano.jp kisofukushima.nagano.jp kitaaiki.nagano.jp komagane.nagano.jp komoro.nagano.jp matsukawa.nagano.jp matsumoto.nagano.jp miasa.nagano.jp minamiaiki.nagano.jp minamimaki.nagano.jp minamiminowa.nagano.jp minowa.nagano.jp miyada.nagano.jp miyota.nagano.jp mochizuki.nagano.jp nagano.nagano.jp nagawa.nagano.jp nagiso.nagano.jp nakagawa.nagano.jp nakano.nagano.jp nozawaonsen.nagano.jp obuse.nagano.jp ogawa.nagano.jp okaya.nagano.jp omachi.nagano.jp omi.nagano.jp ookuwa.nagano.jp ooshika.nagano.jp otaki.nagano.jp otari.nagano.jp sakae.nagano.jp sakaki.nagano.jp saku.nagano.jp sakuho.nagano.jp shimosuwa.nagano.jp shinanomachi.nagano.jp shiojiri.nagano.jp suwa.nagano.jp suzaka.nagano.jp takagi.nagano.jp takamori.nagano.jp takayama.nagano.jp tateshina.nagano.jp tatsuno.nagano.jp togakushi.nagano.jp togura.nagano.jp tomi.nagano.jp ueda.nagano.jp wada.nagano.jp yamagata.nagano.jp yamanouchi.nagano.jp yasaka.nagano.jp yasuoka.nagano.jp chijiwa.nagasaki.jp futsu.nagasaki.jp goto.nagasaki.jp hasami.nagasaki.jp hirado.nagasaki.jp iki.nagasaki.jp isahaya.nagasaki.jp kawatana.nagasaki.jp kuchinotsu.nagasaki.jp matsuura.nagasaki.jp nagasaki.nagasaki.jp obama.nagasaki.jp omura.nagasaki.jp oseto.nagasaki.jp saikai.nagasaki.jp sasebo.nagasaki.jp seihi.nagasaki.jp shimabara.nagasaki.jp shinkamigoto.nagasaki.jp togitsu.nagasaki.jp tsushima.nagasaki.jp unzen.nagasaki.jp ando.nara.jp gose.nara.jp heguri.nara.jp higashiyoshino.nara.jp ikaruga.nara.jp ikoma.nara.jp kamikitayama.nara.jp kanmaki.nara.jp kashiba.nara.jp kashihara.nara.jp katsuragi.nara.jp kawai.nara.jp kawakami.nara.jp kawanishi.nara.jp koryo.nara.jp kurotaki.nara.jp mitsue.nara.jp miyake.nara.jp nara.nara.jp nosegawa.nara.jp oji.nara.jp ouda.nara.jp oyodo.nara.jp sakurai.nara.jp sango.nara.jp shimoichi.nara.jp shimokitayama.nara.jp shinjo.nara.jp soni.nara.jp takatori.nara.jp tawaramoto.nara.jp tenkawa.nara.jp tenri.nara.jp uda.nara.jp yamatokoriyama.nara.jp yamatotakada.nara.jp yamazoe.nara.jp yoshino.nara.jp aga.niigata.jp agano.niigata.jp gosen.niigata.jp itoigawa.niigata.jp izumozaki.niigata.jp joetsu.niigata.jp kamo.niigata.jp kariwa.niigata.jp kashiwazaki.niigata.jp minamiuonuma.niigata.jp mitsuke.niigata.jp muika.niigata.jp murakami.niigata.jp myoko.niigata.jp nagaoka.niigata.jp niigata.niigata.jp ojiya.niigata.jp omi.niigata.jp sado.niigata.jp sanjo.niigata.jp seiro.niigata.jp seirou.niigata.jp sekikawa.niigata.jp shibata.niigata.jp tagami.niigata.jp tainai.niigata.jp tochio.niigata.jp tokamachi.niigata.jp tsubame.niigata.jp tsunan.niigata.jp uonuma.niigata.jp yahiko.niigata.jp yoita.niigata.jp yuzawa.niigata.jp beppu.oita.jp bungoono.oita.jp bungotakada.oita.jp hasama.oita.jp hiji.oita.jp himeshima.oita.jp hita.oita.jp kamitsue.oita.jp kokonoe.oita.jp kuju.oita.jp kunisaki.oita.jp kusu.oita.jp oita.oita.jp saiki.oita.jp taketa.oita.jp tsukumi.oita.jp usa.oita.jp usuki.oita.jp yufu.oita.jp akaiwa.okayama.jp asakuchi.okayama.jp bizen.okayama.jp hayashima.okayama.jp ibara.okayama.jp kagamino.okayama.jp kasaoka.okayama.jp kibichuo.okayama.jp kumenan.okayama.jp kurashiki.okayama.jp maniwa.okayama.jp misaki.okayama.jp nagi.okayama.jp niimi.okayama.jp nishiawakura.okayama.jp okayama.okayama.jp satosho.okayama.jp setouchi.okayama.jp shinjo.okayama.jp shoo.okayama.jp soja.okayama.jp takahashi.okayama.jp tamano.okayama.jp tsuyama.okayama.jp wake.okayama.jp yakage.okayama.jp aguni.okinawa.jp ginowan.okinawa.jp ginoza.okinawa.jp gushikami.okinawa.jp haebaru.okinawa.jp higashi.okinawa.jp hirara.okinawa.jp iheya.okinawa.jp ishigaki.okinawa.jp ishikawa.okinawa.jp itoman.okinawa.jp izena.okinawa.jp kadena.okinawa.jp kin.okinawa.jp kitadaito.okinawa.jp kitanakagusuku.okinawa.jp kumejima.okinawa.jp kunigami.okinawa.jp minamidaito.okinawa.jp motobu.okinawa.jp nago.okinawa.jp naha.okinawa.jp nakagusuku.okinawa.jp nakijin.okinawa.jp nanjo.okinawa.jp nishihara.okinawa.jp ogimi.okinawa.jp okinawa.okinawa.jp onna.okinawa.jp shimoji.okinawa.jp taketomi.okinawa.jp tarama.okinawa.jp tokashiki.okinawa.jp tomigusuku.okinawa.jp tonaki.okinawa.jp urasoe.okinawa.jp uruma.okinawa.jp yaese.okinawa.jp yomitan.okinawa.jp yonabaru.okinawa.jp yonaguni.okinawa.jp zamami.okinawa.jp abeno.osaka.jp chihayaakasaka.osaka.jp chuo.osaka.jp daito.osaka.jp fujiidera.osaka.jp habikino.osaka.jp hannan.osaka.jp higashiosaka.osaka.jp higashisumiyoshi.osaka.jp higashiyodogawa.osaka.jp hirakata.osaka.jp ibaraki.osaka.jp ikeda.osaka.jp izumi.osaka.jp izumiotsu.osaka.jp izumisano.osaka.jp kadoma.osaka.jp kaizuka.osaka.jp kanan.osaka.jp kashiwara.osaka.jp katano.osaka.jp kawachinagano.osaka.jp kishiwada.osaka.jp kita.osaka.jp kumatori.osaka.jp matsubara.osaka.jp minato.osaka.jp minoh.osaka.jp misaki.osaka.jp moriguchi.osaka.jp neyagawa.osaka.jp nishi.osaka.jp nose.osaka.jp osakasayama.osaka.jp sakai.osaka.jp sayama.osaka.jp sennan.osaka.jp settsu.osaka.jp shijonawate.osaka.jp shimamoto.osaka.jp suita.osaka.jp tadaoka.osaka.jp taishi.osaka.jp tajiri.osaka.jp takaishi.osaka.jp takatsuki.osaka.jp tondabayashi.osaka.jp toyonaka.osaka.jp toyono.osaka.jp yao.osaka.jp ariake.saga.jp arita.saga.jp fukudomi.saga.jp genkai.saga.jp hamatama.saga.jp hizen.saga.jp imari.saga.jp kamimine.saga.jp kanzaki.saga.jp karatsu.saga.jp kashima.saga.jp kitagata.saga.jp kitahata.saga.jp kiyama.saga.jp kouhoku.saga.jp kyuragi.saga.jp nishiarita.saga.jp ogi.saga.jp omachi.saga.jp ouchi.saga.jp saga.saga.jp shiroishi.saga.jp taku.saga.jp tara.saga.jp tosu.saga.jp yoshinogari.saga.jp arakawa.saitama.jp asaka.saitama.jp chichibu.saitama.jp fujimi.saitama.jp fujimino.saitama.jp fukaya.saitama.jp hanno.saitama.jp hanyu.saitama.jp hasuda.saitama.jp hatogaya.saitama.jp hatoyama.saitama.jp hidaka.saitama.jp higashichichibu.saitama.jp higashimatsuyama.saitama.jp honjo.saitama.jp ina.saitama.jp iruma.saitama.jp iwatsuki.saitama.jp kamiizumi.saitama.jp kamikawa.saitama.jp kamisato.saitama.jp kasukabe.saitama.jp kawagoe.saitama.jp kawaguchi.saitama.jp kawajima.saitama.jp kazo.saitama.jp kitamoto.saitama.jp koshigaya.saitama.jp kounosu.saitama.jp kuki.saitama.jp kumagaya.saitama.jp matsubushi.saitama.jp minano.saitama.jp misato.saitama.jp miyashiro.saitama.jp miyoshi.saitama.jp moroyama.saitama.jp nagatoro.saitama.jp namegawa.saitama.jp niiza.saitama.jp ogano.saitama.jp ogawa.saitama.jp ogose.saitama.jp okegawa.saitama.jp omiya.saitama.jp otaki.saitama.jp ranzan.saitama.jp ryokami.saitama.jp saitama.saitama.jp sakado.saitama.jp satte.saitama.jp sayama.saitama.jp shiki.saitama.jp shiraoka.saitama.jp soka.saitama.jp sugito.saitama.jp toda.saitama.jp tokigawa.saitama.jp tokorozawa.saitama.jp tsurugashima.saitama.jp urawa.saitama.jp warabi.saitama.jp yashio.saitama.jp yokoze.saitama.jp yono.saitama.jp yorii.saitama.jp yoshida.saitama.jp yoshikawa.saitama.jp yoshimi.saitama.jp aisho.shiga.jp gamo.shiga.jp higashiomi.shiga.jp hikone.shiga.jp koka.shiga.jp konan.shiga.jp kosei.shiga.jp koto.shiga.jp kusatsu.shiga.jp maibara.shiga.jp moriyama.shiga.jp nagahama.shiga.jp nishiazai.shiga.jp notogawa.shiga.jp omihachiman.shiga.jp otsu.shiga.jp ritto.shiga.jp ryuoh.shiga.jp takashima.shiga.jp takatsuki.shiga.jp torahime.shiga.jp toyosato.shiga.jp yasu.shiga.jp akagi.shimane.jp ama.shimane.jp gotsu.shimane.jp hamada.shimane.jp higashiizumo.shimane.jp hikawa.shimane.jp hikimi.shimane.jp izumo.shimane.jp kakinoki.shimane.jp masuda.shimane.jp matsue.shimane.jp misato.shimane.jp nishinoshima.shimane.jp ohda.shimane.jp okinoshima.shimane.jp okuizumo.shimane.jp shimane.shimane.jp tamayu.shimane.jp tsuwano.shimane.jp unnan.shimane.jp yakumo.shimane.jp yasugi.shimane.jp yatsuka.shimane.jp arai.shizuoka.jp atami.shizuoka.jp fuji.shizuoka.jp fujieda.shizuoka.jp fujikawa.shizuoka.jp fujinomiya.shizuoka.jp fukuroi.shizuoka.jp gotemba.shizuoka.jp haibara.shizuoka.jp hamamatsu.shizuoka.jp higashiizu.shizuoka.jp ito.shizuoka.jp iwata.shizuoka.jp izu.shizuoka.jp izunokuni.shizuoka.jp kakegawa.shizuoka.jp kannami.shizuoka.jp kawanehon.shizuoka.jp kawazu.shizuoka.jp kikugawa.shizuoka.jp kosai.shizuoka.jp makinohara.shizuoka.jp matsuzaki.shizuoka.jp minamiizu.shizuoka.jp mishima.shizuoka.jp morimachi.shizuoka.jp nishiizu.shizuoka.jp numazu.shizuoka.jp omaezaki.shizuoka.jp shimada.shizuoka.jp shimizu.shizuoka.jp shimoda.shizuoka.jp shizuoka.shizuoka.jp susono.shizuoka.jp yaizu.shizuoka.jp yoshida.shizuoka.jp ashikaga.tochigi.jp bato.tochigi.jp haga.tochigi.jp ichikai.tochigi.jp iwafune.tochigi.jp kaminokawa.tochigi.jp kanuma.tochigi.jp karasuyama.tochigi.jp kuroiso.tochigi.jp mashiko.tochigi.jp mibu.tochigi.jp moka.tochigi.jp motegi.tochigi.jp nasu.tochigi.jp nasushiobara.tochigi.jp nikko.tochigi.jp nishikata.tochigi.jp nogi.tochigi.jp ohira.tochigi.jp ohtawara.tochigi.jp oyama.tochigi.jp sakura.tochigi.jp sano.tochigi.jp shimotsuke.tochigi.jp shioya.tochigi.jp takanezawa.tochigi.jp tochigi.tochigi.jp tsuga.tochigi.jp ujiie.tochigi.jp utsunomiya.tochigi.jp yaita.tochigi.jp aizumi.tokushima.jp anan.tokushima.jp ichiba.tokushima.jp itano.tokushima.jp kainan.tokushima.jp komatsushima.tokushima.jp matsushige.tokushima.jp mima.tokushima.jp minami.tokushima.jp miyoshi.tokushima.jp mugi.tokushima.jp nakagawa.tokushima.jp naruto.tokushima.jp sanagochi.tokushima.jp shishikui.tokushima.jp tokushima.tokushima.jp wajiki.tokushima.jp adachi.tokyo.jp akiruno.tokyo.jp akishima.tokyo.jp aogashima.tokyo.jp arakawa.tokyo.jp bunkyo.tokyo.jp chiyoda.tokyo.jp chofu.tokyo.jp chuo.tokyo.jp edogawa.tokyo.jp fuchu.tokyo.jp fussa.tokyo.jp hachijo.tokyo.jp hachioji.tokyo.jp hamura.tokyo.jp higashikurume.tokyo.jp higashimurayama.tokyo.jp higashiyamato.tokyo.jp hino.tokyo.jp hinode.tokyo.jp hinohara.tokyo.jp inagi.tokyo.jp itabashi.tokyo.jp katsushika.tokyo.jp kita.tokyo.jp kiyose.tokyo.jp kodaira.tokyo.jp koganei.tokyo.jp kokubunji.tokyo.jp komae.tokyo.jp koto.tokyo.jp kouzushima.tokyo.jp kunitachi.tokyo.jp machida.tokyo.jp meguro.tokyo.jp minato.tokyo.jp mitaka.tokyo.jp mizuho.tokyo.jp musashimurayama.tokyo.jp musashino.tokyo.jp nakano.tokyo.jp nerima.tokyo.jp ogasawara.tokyo.jp okutama.tokyo.jp ome.tokyo.jp oshima.tokyo.jp ota.tokyo.jp setagaya.tokyo.jp shibuya.tokyo.jp shinagawa.tokyo.jp shinjuku.tokyo.jp suginami.tokyo.jp sumida.tokyo.jp tachikawa.tokyo.jp taito.tokyo.jp tama.tokyo.jp toshima.tokyo.jp chizu.tottori.jp hino.tottori.jp kawahara.tottori.jp koge.tottori.jp kotoura.tottori.jp misasa.tottori.jp nanbu.tottori.jp nichinan.tottori.jp sakaiminato.tottori.jp tottori.tottori.jp wakasa.tottori.jp yazu.tottori.jp yonago.tottori.jp asahi.toyama.jp fuchu.toyama.jp fukumitsu.toyama.jp funahashi.toyama.jp himi.toyama.jp imizu.toyama.jp inami.toyama.jp johana.toyama.jp kamiichi.toyama.jp kurobe.toyama.jp nakaniikawa.toyama.jp namerikawa.toyama.jp nanto.toyama.jp nyuzen.toyama.jp oyabe.toyama.jp taira.toyama.jp takaoka.toyama.jp tateyama.toyama.jp toga.toyama.jp tonami.toyama.jp toyama.toyama.jp unazuki.toyama.jp uozu.toyama.jp yamada.toyama.jp arida.wakayama.jp aridagawa.wakayama.jp gobo.wakayama.jp hashimoto.wakayama.jp hidaka.wakayama.jp hirogawa.wakayama.jp inami.wakayama.jp iwade.wakayama.jp kainan.wakayama.jp kamitonda.wakayama.jp katsuragi.wakayama.jp kimino.wakayama.jp kinokawa.wakayama.jp kitayama.wakayama.jp koya.wakayama.jp koza.wakayama.jp kozagawa.wakayama.jp kudoyama.wakayama.jp kushimoto.wakayama.jp mihama.wakayama.jp misato.wakayama.jp nachikatsuura.wakayama.jp shingu.wakayama.jp shirahama.wakayama.jp taiji.wakayama.jp tanabe.wakayama.jp wakayama.wakayama.jp yuasa.wakayama.jp yura.wakayama.jp asahi.yamagata.jp funagata.yamagata.jp higashine.yamagata.jp iide.yamagata.jp kahoku.yamagata.jp kaminoyama.yamagata.jp kaneyama.yamagata.jp kawanishi.yamagata.jp mamurogawa.yamagata.jp mikawa.yamagata.jp murayama.yamagata.jp nagai.yamagata.jp nakayama.yamagata.jp nanyo.yamagata.jp nishikawa.yamagata.jp obanazawa.yamagata.jp oe.yamagata.jp oguni.yamagata.jp ohkura.yamagata.jp oishida.yamagata.jp sagae.yamagata.jp sakata.yamagata.jp sakegawa.yamagata.jp shinjo.yamagata.jp shirataka.yamagata.jp shonai.yamagata.jp takahata.yamagata.jp tendo.yamagata.jp tozawa.yamagata.jp tsuruoka.yamagata.jp yamagata.yamagata.jp yamanobe.yamagata.jp yonezawa.yamagata.jp yuza.yamagata.jp abu.yamaguchi.jp hagi.yamaguchi.jp hikari.yamaguchi.jp hofu.yamaguchi.jp iwakuni.yamaguchi.jp kudamatsu.yamaguchi.jp mitou.yamaguchi.jp nagato.yamaguchi.jp oshima.yamaguchi.jp shimonoseki.yamaguchi.jp shunan.yamaguchi.jp tabuse.yamaguchi.jp tokuyama.yamaguchi.jp toyota.yamaguchi.jp ube.yamaguchi.jp yuu.yamaguchi.jp chuo.yamanashi.jp doshi.yamanashi.jp fuefuki.yamanashi.jp fujikawa.yamanashi.jp fujikawaguchiko.yamanashi.jp fujiyoshida.yamanashi.jp hayakawa.yamanashi.jp hokuto.yamanashi.jp ichikawamisato.yamanashi.jp kai.yamanashi.jp kofu.yamanashi.jp koshu.yamanashi.jp kosuge.yamanashi.jp minami-alps.yamanashi.jp minobu.yamanashi.jp nakamichi.yamanashi.jp nanbu.yamanashi.jp narusawa.yamanashi.jp nirasaki.yamanashi.jp nishikatsura.yamanashi.jp oshino.yamanashi.jp otsuki.yamanashi.jp showa.yamanashi.jp tabayama.yamanashi.jp tsuru.yamanashi.jp uenohara.yamanashi.jp yamanakako.yamanashi.jp yamanashi.yamanashi.jp ke ac.ke co.ke go.ke info.ke me.ke mobi.ke ne.ke or.ke sc.ke kg com.kg edu.kg gov.kg mil.kg net.kg org.kg *.kh ki biz.ki com.ki edu.ki gov.ki info.ki net.ki org.ki km ass.km com.km edu.km gov.km mil.km nom.km org.km prd.km tm.km asso.km coop.km gouv.km medecin.km notaires.km pharmaciens.km presse.km veterinaire.km kn edu.kn gov.kn net.kn org.kn kp com.kp edu.kp gov.kp org.kp rep.kp tra.kp kr ac.kr ai.kr co.kr es.kr go.kr hs.kr io.kr it.kr kg.kr me.kr mil.kr ms.kr ne.kr or.kr pe.kr re.kr sc.kr busan.kr chungbuk.kr chungnam.kr daegu.kr daejeon.kr gangwon.kr gwangju.kr gyeongbuk.kr gyeonggi.kr gyeongnam.kr incheon.kr jeju.kr jeonbuk.kr jeonnam.kr seoul.kr ulsan.kr kw com.kw edu.kw emb.kw gov.kw ind.kw net.kw org.kw ky com.ky edu.ky net.ky org.ky kz com.kz edu.kz gov.kz mil.kz net.kz org.kz la com.la edu.la gov.la info.la int.la net.la org.la per.la lb com.lb edu.lb gov.lb net.lb org.lb lc co.lc com.lc edu.lc gov.lc net.lc org.lc li lk ac.lk assn.lk com.lk edu.lk gov.lk grp.lk hotel.lk int.lk ltd.lk net.lk ngo.lk org.lk sch.lk soc.lk web.lk lr com.lr edu.lr gov.lr net.lr org.lr ls ac.ls biz.ls co.ls edu.ls gov.ls info.ls net.ls org.ls sc.ls lt gov.lt lu lv asn.lv com.lv conf.lv edu.lv gov.lv id.lv mil.lv net.lv org.lv ly com.ly edu.ly gov.ly id.ly med.ly net.ly org.ly plc.ly sch.ly ma ac.ma co.ma gov.ma net.ma org.ma press.ma mc asso.mc tm.mc md me ac.me co.me edu.me gov.me its.me net.me org.me priv.me mg co.mg com.mg edu.mg gov.mg mil.mg nom.mg org.mg prd.mg mh mil mk com.mk edu.mk gov.mk inf.mk name.mk net.mk org.mk ml ac.ml art.ml asso.ml com.ml edu.ml gouv.ml gov.ml info.ml inst.ml net.ml org.ml pr.ml presse.ml *.mm mn edu.mn gov.mn org.mn mo com.mo edu.mo gov.mo net.mo org.mo mobi mp mq mr gov.mr ms com.ms edu.ms gov.ms net.ms org.ms mt com.mt edu.mt net.mt org.mt mu ac.mu co.mu com.mu gov.mu net.mu or.mu org.mu museum mv aero.mv biz.mv com.mv coop.mv edu.mv gov.mv info.mv int.mv mil.mv museum.mv name.mv net.mv org.mv pro.mv mw ac.mw biz.mw co.mw com.mw coop.mw edu.mw gov.mw int.mw net.mw org.mw mx com.mx edu.mx gob.mx net.mx org.mx my biz.my com.my edu.my gov.my mil.my name.my net.my org.my mz ac.mz adv.mz co.mz edu.mz gov.mz mil.mz net.mz org.mz na alt.na co.na com.na gov.na net.na org.na name nc asso.nc nom.nc ne net nf arts.nf com.nf firm.nf info.nf net.nf other.nf per.nf rec.nf store.nf web.nf ng com.ng edu.ng gov.ng i.ng mil.ng mobi.ng name.ng net.ng org.ng sch.ng ni ac.ni biz.ni co.ni com.ni edu.ni gob.ni in.ni info.ni int.ni mil.ni net.ni nom.ni org.ni web.ni nl no fhs.no folkebibl.no fylkesbibl.no idrett.no museum.no priv.no vgs.no dep.no herad.no kommune.no mil.no stat.no aa.no ah.no bu.no fm.no hl.no hm.no jan-mayen.no mr.no nl.no nt.no of.no ol.no oslo.no rl.no sf.no st.no svalbard.no tm.no tr.no va.no vf.no gs.aa.no gs.ah.no gs.bu.no gs.fm.no gs.hl.no gs.hm.no gs.jan-mayen.no gs.mr.no gs.nl.no gs.nt.no gs.of.no gs.ol.no gs.oslo.no gs.rl.no gs.sf.no gs.st.no gs.svalbard.no gs.tm.no gs.tr.no gs.va.no gs.vf.no akrehamn.no xn--krehamn-dxa.no algard.no xn--lgrd-poac.no arna.no bronnoysund.no xn--brnnysund-m8ac.no brumunddal.no bryne.no drobak.no xn--drbak-wua.no egersund.no fetsund.no floro.no xn--flor-jra.no fredrikstad.no hokksund.no honefoss.no xn--hnefoss-q1a.no jessheim.no jorpeland.no xn--jrpeland-54a.no kirkenes.no kopervik.no krokstadelva.no langevag.no xn--langevg-jxa.no leirvik.no mjondalen.no xn--mjndalen-64a.no mo-i-rana.no mosjoen.no xn--mosjen-eya.no nesoddtangen.no orkanger.no osoyro.no xn--osyro-wua.no raholt.no xn--rholt-mra.no sandnessjoen.no xn--sandnessjen-ogb.no skedsmokorset.no slattum.no spjelkavik.no stathelle.no stavern.no stjordalshalsen.no xn--stjrdalshalsen-sqb.no tananger.no tranby.no vossevangen.no aarborte.no aejrie.no afjord.no xn--fjord-lra.no agdenes.no nes.akershus.no aknoluokta.no xn--koluokta-7ya57h.no al.no xn--l-1fa.no alaheadju.no xn--laheadju-7ya.no alesund.no xn--lesund-hua.no alstahaug.no alta.no xn--lt-liac.no alvdal.no amli.no xn--mli-tla.no amot.no xn--mot-tla.no andasuolo.no andebu.no andoy.no xn--andy-ira.no ardal.no xn--rdal-poa.no aremark.no arendal.no xn--s-1fa.no aseral.no xn--seral-lra.no asker.no askim.no askoy.no xn--asky-ira.no askvoll.no asnes.no xn--snes-poa.no audnedaln.no aukra.no aure.no aurland.no aurskog-holand.no xn--aurskog-hland-jnb.no austevoll.no austrheim.no averoy.no xn--avery-yua.no badaddja.no xn--bdddj-mrabd.no xn--brum-voa.no bahcavuotna.no xn--bhcavuotna-s4a.no bahccavuotna.no xn--bhccavuotna-k7a.no baidar.no xn--bidr-5nac.no bajddar.no xn--bjddar-pta.no balat.no xn--blt-elab.no balestrand.no ballangen.no balsfjord.no bamble.no bardu.no barum.no batsfjord.no xn--btsfjord-9za.no bearalvahki.no xn--bearalvhki-y4a.no beardu.no beiarn.no berg.no bergen.no berlevag.no xn--berlevg-jxa.no bievat.no xn--bievt-0qa.no bindal.no birkenes.no bjarkoy.no xn--bjarky-fya.no bjerkreim.no bjugn.no bodo.no xn--bod-2na.no bokn.no bomlo.no xn--bmlo-gra.no bremanger.no bronnoy.no xn--brnny-wuac.no budejju.no nes.buskerud.no bygland.no bykle.no cahcesuolo.no xn--hcesuolo-7ya35b.no davvenjarga.no xn--davvenjrga-y4a.no davvesiida.no deatnu.no dielddanuorri.no divtasvuodna.no divttasvuotna.no donna.no xn--dnna-gra.no dovre.no drammen.no drangedal.no dyroy.no xn--dyry-ira.no eid.no eidfjord.no eidsberg.no eidskog.no eidsvoll.no eigersund.no elverum.no enebakk.no engerdal.no etne.no etnedal.no evenassi.no xn--eveni-0qa01ga.no evenes.no evje-og-hornnes.no farsund.no fauske.no fedje.no fet.no finnoy.no xn--finny-yua.no fitjar.no fjaler.no fjell.no fla.no xn--fl-zia.no flakstad.no flatanger.no flekkefjord.no flesberg.no flora.no folldal.no forde.no xn--frde-gra.no forsand.no fosnes.no xn--frna-woa.no frana.no frei.no frogn.no froland.no frosta.no froya.no xn--frya-hra.no fuoisku.no fuossko.no fusa.no fyresdal.no gaivuotna.no xn--givuotna-8ya.no galsa.no xn--gls-elac.no gamvik.no gangaviika.no xn--ggaviika-8ya47h.no gaular.no gausdal.no giehtavuoatna.no gildeskal.no xn--gildeskl-g0a.no giske.no gjemnes.no gjerdrum.no gjerstad.no gjesdal.no gjovik.no xn--gjvik-wua.no gloppen.no gol.no gran.no grane.no granvin.no gratangen.no grimstad.no grong.no grue.no gulen.no guovdageaidnu.no ha.no xn--h-2fa.no habmer.no xn--hbmer-xqa.no hadsel.no xn--hgebostad-g3a.no hagebostad.no halden.no halsa.no hamar.no hamaroy.no hammarfeasta.no xn--hmmrfeasta-s4ac.no hammerfest.no hapmir.no xn--hpmir-xqa.no haram.no hareid.no harstad.no hasvik.no hattfjelldal.no haugesund.no os.hedmark.no valer.hedmark.no xn--vler-qoa.hedmark.no hemne.no hemnes.no hemsedal.no hitra.no hjartdal.no hjelmeland.no hobol.no xn--hobl-ira.no hof.no hol.no hole.no holmestrand.no holtalen.no xn--holtlen-hxa.no os.hordaland.no hornindal.no horten.no hoyanger.no xn--hyanger-q1a.no hoylandet.no xn--hylandet-54a.no hurdal.no hurum.no hvaler.no hyllestad.no ibestad.no inderoy.no xn--indery-fya.no iveland.no ivgu.no jevnaker.no jolster.no xn--jlster-bya.no jondal.no kafjord.no xn--kfjord-iua.no karasjohka.no xn--krjohka-hwab49j.no karasjok.no karlsoy.no karmoy.no xn--karmy-yua.no kautokeino.no klabu.no xn--klbu-woa.no klepp.no kongsberg.no kongsvinger.no kraanghke.no xn--kranghke-b0a.no kragero.no xn--krager-gya.no kristiansand.no kristiansund.no krodsherad.no xn--krdsherad-m8a.no xn--kvfjord-nxa.no xn--kvnangen-k0a.no kvafjord.no kvalsund.no kvam.no kvanangen.no kvinesdal.no kvinnherad.no kviteseid.no kvitsoy.no xn--kvitsy-fya.no laakesvuemie.no xn--lrdal-sra.no lahppi.no xn--lhppi-xqa.no lardal.no larvik.no lavagis.no lavangen.no leangaviika.no xn--leagaviika-52b.no lebesby.no leikanger.no leirfjord.no leka.no leksvik.no lenvik.no lerdal.no lesja.no levanger.no lier.no lierne.no lillehammer.no lillesand.no lindas.no xn--linds-pra.no lindesnes.no loabat.no xn--loabt-0qa.no lodingen.no xn--ldingen-q1a.no lom.no loppa.no lorenskog.no xn--lrenskog-54a.no loten.no xn--lten-gra.no lund.no lunner.no luroy.no xn--lury-ira.no luster.no lyngdal.no lyngen.no malatvuopmi.no xn--mlatvuopmi-s4a.no malselv.no xn--mlselv-iua.no malvik.no mandal.no marker.no marnardal.no masfjorden.no masoy.no xn--msy-ula0h.no matta-varjjat.no xn--mtta-vrjjat-k7af.no meland.no meldal.no melhus.no meloy.no xn--mely-ira.no meraker.no xn--merker-kua.no midsund.no midtre-gauldal.no moareke.no xn--moreke-jua.no modalen.no modum.no molde.no heroy.more-og-romsdal.no sande.more-og-romsdal.no xn--hery-ira.xn--mre-og-romsdal-qqb.no sande.xn--mre-og-romsdal-qqb.no moskenes.no moss.no mosvik.no muosat.no xn--muost-0qa.no naamesjevuemie.no xn--nmesjevuemie-tcba.no xn--nry-yla5g.no namdalseid.no namsos.no namsskogan.no nannestad.no naroy.no narviika.no narvik.no naustdal.no navuotna.no xn--nvuotna-hwa.no nedre-eiker.no nesna.no nesodden.no nesseby.no nesset.no nissedal.no nittedal.no nord-aurdal.no nord-fron.no nord-odal.no norddal.no nordkapp.no bo.nordland.no xn--b-5ga.nordland.no heroy.nordland.no xn--hery-ira.nordland.no nordre-land.no nordreisa.no nore-og-uvdal.no notodden.no notteroy.no xn--nttery-byae.no odda.no oksnes.no xn--ksnes-uua.no omasvuotna.no oppdal.no oppegard.no xn--oppegrd-ixa.no orkdal.no orland.no xn--rland-uua.no orskog.no xn--rskog-uua.no orsta.no xn--rsta-fra.no osen.no osteroy.no xn--ostery-fya.no valer.ostfold.no xn--vler-qoa.xn--stfold-9xa.no ostre-toten.no xn--stre-toten-zcb.no overhalla.no ovre-eiker.no xn--vre-eiker-k8a.no oyer.no xn--yer-zna.no oygarden.no xn--ygarden-p1a.no oystre-slidre.no xn--ystre-slidre-ujb.no porsanger.no porsangu.no xn--porsgu-sta26f.no porsgrunn.no rade.no xn--rde-ula.no radoy.no xn--rady-ira.no xn--rlingen-mxa.no rahkkeravju.no xn--rhkkervju-01af.no raisa.no xn--risa-5na.no rakkestad.no ralingen.no rana.no randaberg.no rauma.no rendalen.no rennebu.no rennesoy.no xn--rennesy-v1a.no rindal.no ringebu.no ringerike.no ringsaker.no risor.no xn--risr-ira.no rissa.no roan.no rodoy.no xn--rdy-0nab.no rollag.no romsa.no romskog.no xn--rmskog-bya.no roros.no xn--rros-gra.no rost.no xn--rst-0na.no royken.no xn--ryken-vua.no royrvik.no xn--ryrvik-bya.no ruovat.no rygge.no salangen.no salat.no xn--slat-5na.no xn--slt-elab.no saltdal.no samnanger.no sandefjord.no sandnes.no sandoy.no xn--sandy-yua.no sarpsborg.no sauda.no sauherad.no sel.no selbu.no selje.no seljord.no siellak.no sigdal.no siljan.no sirdal.no skanit.no xn--sknit-yqa.no skanland.no xn--sknland-fxa.no skaun.no skedsmo.no ski.no skien.no skierva.no xn--skierv-uta.no skiptvet.no skjak.no xn--skjk-soa.no skjervoy.no xn--skjervy-v1a.no skodje.no smola.no xn--smla-hra.no snaase.no xn--snase-nra.no snasa.no xn--snsa-roa.no snillfjord.no snoasa.no sogndal.no sogne.no xn--sgne-gra.no sokndal.no sola.no solund.no somna.no xn--smna-gra.no sondre-land.no xn--sndre-land-0cb.no songdalen.no sor-aurdal.no xn--sr-aurdal-l8a.no sor-fron.no xn--sr-fron-q1a.no sor-odal.no xn--sr-odal-q1a.no sor-varanger.no xn--sr-varanger-ggb.no sorfold.no xn--srfold-bya.no sorreisa.no xn--srreisa-q1a.no sortland.no sorum.no xn--srum-gra.no spydeberg.no stange.no stavanger.no steigen.no steinkjer.no stjordal.no xn--stjrdal-s1a.no stokke.no stor-elvdal.no stord.no stordal.no storfjord.no strand.no stranda.no stryn.no sula.no suldal.no sund.no sunndal.no surnadal.no sveio.no svelvik.no sykkylven.no tana.no bo.telemark.no xn--b-5ga.telemark.no time.no tingvoll.no tinn.no tjeldsund.no tjome.no xn--tjme-hra.no tokke.no tolga.no tonsberg.no xn--tnsberg-q1a.no torsken.no xn--trna-woa.no trana.no tranoy.no xn--trany-yua.no troandin.no trogstad.no xn--trgstad-r1a.no tromsa.no tromso.no xn--troms-zua.no trondheim.no trysil.no tvedestrand.no tydal.no tynset.no tysfjord.no tysnes.no xn--tysvr-vra.no tysvar.no ullensaker.no ullensvang.no ulvik.no unjarga.no xn--unjrga-rta.no utsira.no vaapste.no vadso.no xn--vads-jra.no xn--vry-yla5g.no vaga.no xn--vg-yiab.no vagan.no xn--vgan-qoa.no vagsoy.no xn--vgsy-qoa0j.no vaksdal.no valle.no vang.no vanylven.no vardo.no xn--vard-jra.no varggat.no xn--vrggt-xqad.no varoy.no vefsn.no vega.no vegarshei.no xn--vegrshei-c0a.no vennesla.no verdal.no verran.no vestby.no sande.vestfold.no vestnes.no vestre-slidre.no vestre-toten.no vestvagoy.no xn--vestvgy-ixa6o.no vevelstad.no vik.no vikna.no vindafjord.no voagat.no volda.no voss.no *.np nr biz.nr com.nr edu.nr gov.nr info.nr net.nr org.nr nu nz ac.nz co.nz cri.nz geek.nz gen.nz govt.nz health.nz iwi.nz kiwi.nz maori.nz xn--mori-qsa.nz mil.nz net.nz org.nz parliament.nz school.nz om co.om com.om edu.om gov.om med.om museum.om net.om org.om pro.om onion org pa abo.pa ac.pa com.pa edu.pa gob.pa ing.pa med.pa net.pa nom.pa org.pa sld.pa pe com.pe edu.pe gob.pe mil.pe net.pe nom.pe org.pe pf com.pf edu.pf org.pf *.pg ph com.ph edu.ph gov.ph i.ph mil.ph net.ph ngo.ph org.ph pk ac.pk biz.pk com.pk edu.pk fam.pk gkp.pk gob.pk gog.pk gok.pk gop.pk gos.pk gov.pk net.pk org.pk web.pk pl com.pl net.pl org.pl agro.pl aid.pl atm.pl auto.pl biz.pl edu.pl gmina.pl gsm.pl info.pl mail.pl media.pl miasta.pl mil.pl nieruchomosci.pl nom.pl pc.pl powiat.pl priv.pl realestate.pl rel.pl sex.pl shop.pl sklep.pl sos.pl szkola.pl targi.pl tm.pl tourism.pl travel.pl turystyka.pl gov.pl ap.gov.pl griw.gov.pl ic.gov.pl is.gov.pl kmpsp.gov.pl konsulat.gov.pl kppsp.gov.pl kwp.gov.pl kwpsp.gov.pl mup.gov.pl mw.gov.pl oia.gov.pl oirm.gov.pl oke.gov.pl oow.gov.pl oschr.gov.pl oum.gov.pl pa.gov.pl pinb.gov.pl piw.gov.pl po.gov.pl pr.gov.pl psp.gov.pl psse.gov.pl pup.gov.pl rzgw.gov.pl sa.gov.pl sdn.gov.pl sko.gov.pl so.gov.pl sr.gov.pl starostwo.gov.pl ug.gov.pl ugim.gov.pl um.gov.pl umig.gov.pl upow.gov.pl uppo.gov.pl us.gov.pl uw.gov.pl uzs.gov.pl wif.gov.pl wiih.gov.pl winb.gov.pl wios.gov.pl witd.gov.pl wiw.gov.pl wkz.gov.pl wsa.gov.pl wskr.gov.pl wsse.gov.pl wuoz.gov.pl wzmiuw.gov.pl zp.gov.pl zpisdn.gov.pl augustow.pl babia-gora.pl bedzin.pl beskidy.pl bialowieza.pl bialystok.pl bielawa.pl bieszczady.pl boleslawiec.pl bydgoszcz.pl bytom.pl cieszyn.pl czeladz.pl czest.pl dlugoleka.pl elblag.pl elk.pl glogow.pl gniezno.pl gorlice.pl grajewo.pl ilawa.pl jaworzno.pl jelenia-gora.pl jgora.pl kalisz.pl karpacz.pl kartuzy.pl kaszuby.pl katowice.pl kazimierz-dolny.pl kepno.pl ketrzyn.pl klodzko.pl kobierzyce.pl kolobrzeg.pl konin.pl konskowola.pl kutno.pl lapy.pl lebork.pl legnica.pl lezajsk.pl limanowa.pl lomza.pl lowicz.pl lubin.pl lukow.pl malbork.pl malopolska.pl mazowsze.pl mazury.pl mielec.pl mielno.pl mragowo.pl naklo.pl nowaruda.pl nysa.pl olawa.pl olecko.pl olkusz.pl olsztyn.pl opoczno.pl opole.pl ostroda.pl ostroleka.pl ostrowiec.pl ostrowwlkp.pl pila.pl pisz.pl podhale.pl podlasie.pl polkowice.pl pomorskie.pl pomorze.pl prochowice.pl pruszkow.pl przeworsk.pl pulawy.pl radom.pl rawa-maz.pl rybnik.pl rzeszow.pl sanok.pl sejny.pl skoczow.pl slask.pl slupsk.pl sosnowiec.pl stalowa-wola.pl starachowice.pl stargard.pl suwalki.pl swidnica.pl swiebodzin.pl swinoujscie.pl szczecin.pl szczytno.pl tarnobrzeg.pl tgory.pl turek.pl tychy.pl ustka.pl walbrzych.pl warmia.pl warszawa.pl waw.pl wegrow.pl wielun.pl wlocl.pl wloclawek.pl wodzislaw.pl wolomin.pl wroclaw.pl zachpomor.pl zagan.pl zarow.pl zgora.pl zgorzelec.pl pm pn co.pn edu.pn gov.pn net.pn org.pn post pr biz.pr com.pr edu.pr gov.pr info.pr isla.pr name.pr net.pr org.pr pro.pr ac.pr est.pr prof.pr pro aaa.pro aca.pro acct.pro avocat.pro bar.pro cpa.pro eng.pro jur.pro law.pro med.pro recht.pro ps com.ps edu.ps gov.ps net.ps org.ps plo.ps sec.ps pt com.pt edu.pt gov.pt int.pt net.pt nome.pt org.pt publ.pt pw gov.pw py com.py coop.py edu.py gov.py mil.py net.py org.py qa com.qa edu.qa gov.qa mil.qa name.qa net.qa org.qa sch.qa re asso.re com.re ro arts.ro com.ro firm.ro info.ro nom.ro nt.ro org.ro rec.ro store.ro tm.ro www.ro rs ac.rs co.rs edu.rs gov.rs in.rs org.rs ru rw ac.rw co.rw coop.rw gov.rw mil.rw net.rw org.rw sa com.sa edu.sa gov.sa med.sa net.sa org.sa pub.sa sch.sa sb com.sb edu.sb gov.sb net.sb org.sb sc com.sc edu.sc gov.sc net.sc org.sc sd com.sd edu.sd gov.sd info.sd med.sd net.sd org.sd tv.sd se a.se ac.se b.se bd.se brand.se c.se d.se e.se f.se fh.se fhsk.se fhv.se g.se h.se i.se k.se komforb.se kommunalforbund.se komvux.se l.se lanbib.se m.se n.se naturbruksgymn.se o.se org.se p.se parti.se pp.se press.se r.se s.se t.se tm.se u.se w.se x.se y.se z.se sg com.sg edu.sg gov.sg net.sg org.sg sh com.sh gov.sh mil.sh net.sh org.sh si sj sk sl com.sl edu.sl gov.sl net.sl org.sl sm sn art.sn com.sn edu.sn gouv.sn org.sn perso.sn univ.sn so com.so edu.so gov.so me.so net.so org.so sr ss biz.ss co.ss com.ss edu.ss gov.ss me.ss net.ss org.ss sch.ss st co.st com.st consulado.st edu.st embaixada.st mil.st net.st org.st principe.st saotome.st store.st su sv com.sv edu.sv gob.sv org.sv red.sv sx gov.sx sy com.sy edu.sy gov.sy mil.sy net.sy org.sy sz ac.sz co.sz org.sz tc td tel tf tg th ac.th co.th go.th in.th mi.th net.th or.th tj ac.tj biz.tj co.tj com.tj edu.tj go.tj gov.tj int.tj mil.tj name.tj net.tj nic.tj org.tj test.tj web.tj tk tl gov.tl tm co.tm com.tm edu.tm gov.tm mil.tm net.tm nom.tm org.tm tn com.tn ens.tn fin.tn gov.tn ind.tn info.tn intl.tn mincom.tn nat.tn net.tn org.tn perso.tn tourism.tn to com.to edu.to gov.to mil.to net.to org.to tr av.tr bbs.tr bel.tr biz.tr com.tr dr.tr edu.tr gen.tr gov.tr info.tr k12.tr kep.tr mil.tr name.tr net.tr org.tr pol.tr tel.tr tsk.tr tv.tr web.tr nc.tr gov.nc.tr tt biz.tt co.tt com.tt edu.tt gov.tt info.tt mil.tt name.tt net.tt org.tt pro.tt tv tw club.tw com.tw ebiz.tw edu.tw game.tw gov.tw idv.tw mil.tw net.tw org.tw tz ac.tz co.tz go.tz hotel.tz info.tz me.tz mil.tz mobi.tz ne.tz or.tz sc.tz tv.tz ua com.ua edu.ua gov.ua in.ua net.ua org.ua cherkassy.ua cherkasy.ua chernigov.ua chernihiv.ua chernivtsi.ua chernovtsy.ua ck.ua cn.ua cr.ua crimea.ua cv.ua dn.ua dnepropetrovsk.ua dnipropetrovsk.ua donetsk.ua dp.ua if.ua ivano-frankivsk.ua kh.ua kharkiv.ua kharkov.ua kherson.ua khmelnitskiy.ua khmelnytskyi.ua kiev.ua kirovograd.ua km.ua kr.ua kropyvnytskyi.ua krym.ua ks.ua kv.ua kyiv.ua lg.ua lt.ua lugansk.ua luhansk.ua lutsk.ua lv.ua lviv.ua mk.ua mykolaiv.ua nikolaev.ua od.ua odesa.ua odessa.ua pl.ua poltava.ua rivne.ua rovno.ua rv.ua sb.ua sebastopol.ua sevastopol.ua sm.ua sumy.ua te.ua ternopil.ua uz.ua uzhgorod.ua uzhhorod.ua vinnica.ua vinnytsia.ua vn.ua volyn.ua yalta.ua zakarpattia.ua zaporizhzhe.ua zaporizhzhia.ua zhitomir.ua zhytomyr.ua zp.ua zt.ua ug ac.ug co.ug com.ug edu.ug go.ug gov.ug mil.ug ne.ug or.ug org.ug sc.ug us.ug uk ac.uk co.uk gov.uk ltd.uk me.uk net.uk nhs.uk org.uk plc.uk police.uk *.sch.uk us dni.us isa.us nsn.us ak.us al.us ar.us as.us az.us ca.us co.us ct.us dc.us de.us fl.us ga.us gu.us hi.us ia.us id.us il.us in.us ks.us ky.us la.us ma.us md.us me.us mi.us mn.us mo.us ms.us mt.us nc.us nd.us ne.us nh.us nj.us nm.us nv.us ny.us oh.us ok.us or.us pa.us pr.us ri.us sc.us sd.us tn.us tx.us ut.us va.us vi.us vt.us wa.us wi.us wv.us wy.us k12.ak.us k12.al.us k12.ar.us k12.as.us k12.az.us k12.ca.us k12.co.us k12.ct.us k12.dc.us k12.fl.us k12.ga.us k12.gu.us k12.ia.us k12.id.us k12.il.us k12.in.us k12.ks.us k12.ky.us k12.la.us k12.ma.us k12.md.us k12.me.us k12.mi.us k12.mn.us k12.mo.us k12.ms.us k12.mt.us k12.nc.us k12.ne.us k12.nh.us k12.nj.us k12.nm.us k12.nv.us k12.ny.us k12.oh.us k12.ok.us k12.or.us k12.pa.us k12.pr.us k12.sc.us k12.tn.us k12.tx.us k12.ut.us k12.va.us k12.vi.us k12.vt.us k12.wa.us k12.wi.us cc.ak.us lib.ak.us cc.al.us lib.al.us cc.ar.us lib.ar.us cc.as.us lib.as.us cc.az.us lib.az.us cc.ca.us lib.ca.us cc.co.us lib.co.us cc.ct.us lib.ct.us cc.dc.us lib.dc.us cc.de.us cc.fl.us cc.ga.us cc.gu.us cc.hi.us cc.ia.us cc.id.us cc.il.us cc.in.us cc.ks.us cc.ky.us cc.la.us cc.ma.us cc.md.us cc.me.us cc.mi.us cc.mn.us cc.mo.us cc.ms.us cc.mt.us cc.nc.us cc.nd.us cc.ne.us cc.nh.us cc.nj.us cc.nm.us cc.nv.us cc.ny.us cc.oh.us cc.ok.us cc.or.us cc.pa.us cc.pr.us cc.ri.us cc.sc.us cc.sd.us cc.tn.us cc.tx.us cc.ut.us cc.va.us cc.vi.us cc.vt.us cc.wa.us cc.wi.us cc.wv.us cc.wy.us k12.wy.us lib.fl.us lib.ga.us lib.gu.us lib.hi.us lib.ia.us lib.id.us lib.il.us lib.in.us lib.ks.us lib.ky.us lib.la.us lib.ma.us lib.md.us lib.me.us lib.mi.us lib.mn.us lib.mo.us lib.ms.us lib.mt.us lib.nc.us lib.nd.us lib.ne.us lib.nh.us lib.nj.us lib.nm.us lib.nv.us lib.ny.us lib.oh.us lib.ok.us lib.or.us lib.pa.us lib.pr.us lib.ri.us lib.sc.us lib.sd.us lib.tn.us lib.tx.us lib.ut.us lib.va.us lib.vi.us lib.vt.us lib.wa.us lib.wi.us lib.wy.us chtr.k12.ma.us paroch.k12.ma.us pvt.k12.ma.us ann-arbor.mi.us cog.mi.us dst.mi.us eaton.mi.us gen.mi.us mus.mi.us tec.mi.us washtenaw.mi.us uy com.uy edu.uy gub.uy mil.uy net.uy org.uy uz co.uz com.uz net.uz org.uz va vc com.vc edu.vc gov.vc mil.vc net.vc org.vc ve arts.ve bib.ve co.ve com.ve e12.ve edu.ve emprende.ve firm.ve gob.ve gov.ve info.ve int.ve mil.ve net.ve nom.ve org.ve rar.ve rec.ve store.ve tec.ve web.ve vg edu.vg vi co.vi com.vi k12.vi net.vi org.vi vn ac.vn ai.vn biz.vn com.vn edu.vn gov.vn health.vn id.vn info.vn int.vn io.vn name.vn net.vn org.vn pro.vn angiang.vn bacgiang.vn backan.vn baclieu.vn bacninh.vn baria-vungtau.vn bentre.vn binhdinh.vn binhduong.vn binhphuoc.vn binhthuan.vn camau.vn cantho.vn caobang.vn daklak.vn daknong.vn danang.vn dienbien.vn dongnai.vn dongthap.vn gialai.vn hagiang.vn haiduong.vn haiphong.vn hanam.vn hanoi.vn hatinh.vn haugiang.vn hoabinh.vn hungyen.vn khanhhoa.vn kiengiang.vn kontum.vn laichau.vn lamdong.vn langson.vn laocai.vn longan.vn namdinh.vn nghean.vn ninhbinh.vn ninhthuan.vn phutho.vn phuyen.vn quangbinh.vn quangnam.vn quangngai.vn quangninh.vn quangtri.vn soctrang.vn sonla.vn tayninh.vn thaibinh.vn thainguyen.vn thanhhoa.vn thanhphohochiminh.vn thuathienhue.vn tiengiang.vn travinh.vn tuyenquang.vn vinhlong.vn vinhphuc.vn yenbai.vn vu com.vu edu.vu net.vu org.vu wf ws com.ws edu.ws gov.ws net.ws org.ws yt xn--mgbaam7a8h xn--y9a3aq xn--54b7fta0cc xn--90ae xn--mgbcpq6gpa1a xn--90ais xn--fiqs8s xn--fiqz9s xn--lgbbat1ad8j xn--wgbh1c xn--e1a4c xn--qxa6a xn--mgbah1a3hjkrd xn--node xn--qxam xn--j6w193g xn--gmqw5a.xn--j6w193g xn--55qx5d.xn--j6w193g xn--mxtq1m.xn--j6w193g xn--wcvs22d.xn--j6w193g xn--uc0atv.xn--j6w193g xn--od0alg.xn--j6w193g xn--2scrj9c xn--3hcrj9c xn--45br5cyl xn--h2breg3eve xn--h2brj9c8c xn--mgbgu82a xn--rvc1e0am3e xn--h2brj9c xn--mgbbh1a xn--mgbbh1a71e xn--fpcrj9c3d xn--gecrj9c xn--s9brj9c xn--45brj9c xn--xkc2dl3a5ee0h xn--mgba3a4f16a xn--mgba3a4fra xn--mgbtx2b xn--mgbayh7gpa xn--3e0b707e xn--80ao21a xn--q7ce6a xn--fzc2c9e2c xn--xkc2al3hye2a xn--mgbc0a9azcg xn--d1alf xn--l1acc xn--mix891f xn--mix082f xn--mgbx4cd0ab xn--mgb9awbf xn--mgbai9azgqp6j xn--mgbai9a5eva00b xn--ygbi2ammx xn--90a3ac xn--80au.xn--90a3ac xn--90azh.xn--90a3ac xn--d1at.xn--90a3ac xn--c1avg.xn--90a3ac xn--o1ac.xn--90a3ac xn--o1ach.xn--90a3ac xn--p1ai xn--wgbl6a xn--mgberp4a5d4ar xn--mgberp4a5d4a87g xn--mgbqly7c0a67fbc xn--mgbqly7cvafr xn--mgbpl2fh xn--yfro4i67o xn--clchc0ea0b2g2a9gcd xn--ogbpf8fl xn--mgbtf8fl xn--o3cw4h xn--o3cyx2a.xn--o3cw4h xn--12co0c3b4eva.xn--o3cw4h xn--m3ch0j3a.xn--o3cw4h xn--h3cuzk1di.xn--o3cw4h xn--12c1fe0br.xn--o3cw4h xn--12cfi8ixb8l.xn--o3cw4h xn--pgbs0dh xn--kpry57d xn--kprw13d xn--nnx388a xn--j1amh xn--mgb2ddes xxx ye com.ye edu.ye gov.ye mil.ye net.ye org.ye ac.za agric.za alt.za co.za edu.za gov.za grondar.za law.za mil.za net.za ngo.za nic.za nis.za nom.za org.za school.za tm.za web.za zm ac.zm biz.zm co.zm com.zm edu.zm gov.zm info.zm mil.zm net.zm org.zm sch.zm zw ac.zw co.zw gov.zw mil.zw org.zw aaa aarp abb abbott abbvie abc able abogado abudhabi academy accenture accountant accountants aco actor ads adult aeg aetna afl africa agakhan agency aig airbus airforce airtel akdn alibaba alipay allfinanz allstate ally alsace alstom amazon americanexpress americanfamily amex amfam amica amsterdam analytics android anquan anz aol apartments app apple aquarelle arab aramco archi army art arte asda associates athleta attorney auction audi audible audio auspost author auto autos aws axa azure baby baidu banamex band bank bar barcelona barclaycard barclays barefoot bargains baseball basketball bauhaus bayern bbc bbt bbva bcg bcn beats beauty beer bentley berlin best bestbuy bet bharti bible bid bike bing bingo bio black blackfriday blockbuster blog bloomberg blue bms bmw bnpparibas boats boehringer bofa bom bond boo book booking bosch bostik boston bot boutique box bradesco bridgestone broadway broker brother brussels build builders business buy buzz bzh cab cafe cal call calvinklein cam camera camp canon capetown capital capitalone car caravan cards care career careers cars casa case cash casino catering catholic cba cbn cbre center ceo cern cfa cfd chanel channel charity chase chat cheap chintai christmas chrome church cipriani circle cisco citadel citi citic city claims cleaning click clinic clinique clothing cloud club clubmed coach codes coffee college cologne commbank community company compare computer comsec condos construction consulting contact contractors cooking cool corsica country coupon coupons courses cpa credit creditcard creditunion cricket crown crs cruise cruises cuisinella cymru cyou dad dance data date dating datsun day dclk dds deal dealer deals degree delivery dell deloitte delta democrat dental dentist desi design dev dhl diamonds diet digital direct directory discount discover dish diy dnp docs doctor dog domains dot download drive dtv dubai dunlop dupont durban dvag dvr earth eat eco edeka education email emerck energy engineer engineering enterprises epson equipment ericsson erni esq estate eurovision eus events exchange expert exposed express extraspace fage fail fairwinds faith family fan fans farm farmers fashion fast fedex feedback ferrari ferrero fidelity fido film final finance financial fire firestone firmdale fish fishing fit fitness flickr flights flir florist flowers fly foo food football ford forex forsale forum foundation fox free fresenius frl frogans frontier ftr fujitsu fun fund furniture futbol fyi gal gallery gallo gallup game games gap garden gay gbiz gdn gea gent genting george ggee gift gifts gives giving glass gle global globo gmail gmbh gmo gmx godaddy gold goldpoint golf goo goodyear goog google gop got grainger graphics gratis green gripe grocery group gucci guge guide guitars guru hair hamburg hangout haus hbo hdfc hdfcbank health healthcare help helsinki here hermes hiphop hisamitsu hitachi hiv hkt hockey holdings holiday homedepot homegoods homes homesense honda horse hospital host hosting hot hotels hotmail house how hsbc hughes hyatt hyundai ibm icbc ice icu ieee ifm ikano imamat imdb immo immobilien inc industries infiniti ing ink institute insurance insure international intuit investments ipiranga irish ismaili ist istanbul itau itv jaguar java jcb jeep jetzt jewelry jio jll jmp jnj joburg jot joy jpmorgan jprs juegos juniper kaufen kddi kerryhotels kerryproperties kfh kia kids kim kindle kitchen kiwi koeln komatsu kosher kpmg kpn krd kred kuokgroup kyoto lacaixa lamborghini lamer lancaster land landrover lanxess lasalle lat latino latrobe law lawyer lds lease leclerc lefrak legal lego lexus lgbt lidl life lifeinsurance lifestyle lighting like lilly limited limo lincoln link live living llc llp loan loans locker locus lol london lotte lotto love lpl lplfinancial ltd ltda lundbeck luxe luxury madrid maif maison makeup man management mango map market marketing markets marriott marshalls mattel mba mckinsey med media meet melbourne meme memorial men menu merck merckmsd miami microsoft mini mint mit mitsubishi mlb mls mma mobile moda moe moi mom monash money monster mormon mortgage moscow moto motorcycles mov movie msd mtn mtr music nab nagoya navy nba nec netbank netflix network neustar new news next nextdirect nexus nfl ngo nhk nico nike nikon ninja nissan nissay nokia norton now nowruz nowtv nra nrw ntt nyc obi observer office okinawa olayan olayangroup ollo omega one ong onl online ooo open oracle orange organic origins osaka otsuka ott ovh page panasonic paris pars partners parts party pay pccw pet pfizer pharmacy phd philips phone photo photography photos physio pics pictet pictures pid pin ping pink pioneer pizza place play playstation plumbing plus pnc pohl poker politie porn pramerica praxi press prime prod productions prof progressive promo properties property protection pru prudential pub pwc qpon quebec quest racing radio read realestate realtor realty recipes red redstone redumbrella rehab reise reisen reit reliance ren rent rentals repair report republican rest restaurant review reviews rexroth rich richardli ricoh ril rio rip rocks rodeo rogers room rsvp rugby ruhr run rwe ryukyu saarland safe safety sakura sale salon samsclub samsung sandvik sandvikcoromant sanofi sap sarl sas save saxo sbi sbs scb schaeffler schmidt scholarships school schule schwarz science scot search seat secure security seek select sener services seven sew sex sexy sfr shangrila sharp shell shia shiksha shoes shop shopping shouji show silk sina singles site ski skin sky skype sling smart smile sncf soccer social softbank software sohu solar solutions song sony soy spa space sport spot srl stada staples star statebank statefarm stc stcgroup stockholm storage store stream studio study style sucks supplies supply support surf surgery suzuki swatch swiss sydney systems tab taipei talk taobao target tatamotors tatar tattoo tax taxi tci tdk team tech technology temasek tennis teva thd theater theatre tiaa tickets tienda tips tires tirol tjmaxx tjx tkmaxx tmall today tokyo tools top toray toshiba total tours town toyota toys trade trading training travel travelers travelersinsurance trust trv tube tui tunes tushu tvs ubank ubs unicom university uno uol ups vacations vana vanguard vegas ventures verisign versicherung vet viajes video vig viking villas vin vip virgin visa vision viva vivo vlaanderen vodka volvo vote voting voto voyage wales walmart walter wang wanggou watch watches weather weatherchannel webcam weber website wed wedding weibo weir whoswho wien wiki williamhill win windows wine winners wme wolterskluwer woodside work works world wow wtc wtf xbox xerox xihuan xin xn--11b4c3d xn--1ck2e1b xn--1qqw23a xn--30rr7y xn--3bst00m xn--3ds443g xn--3pxu8k xn--42c2d9a xn--45q11c xn--4gbrim xn--55qw42g xn--55qx5d xn--5su34j936bgsg xn--5tzm5g xn--6frz82g xn--6qq986b3xl xn--80adxhks xn--80aqecdr1a xn--80asehdb xn--80aswg xn--8y0a063a xn--9dbq2a xn--9et52u xn--9krt00a xn--b4w605ferd xn--bck1b9a5dre4c xn--c1avg xn--c2br7g xn--cck2b3b xn--cckwcxetd xn--cg4bki xn--czr694b xn--czrs0t xn--czru2d xn--d1acj3b xn--eckvdtc9d xn--efvy88h xn--fct429k xn--fhbei xn--fiq228c5hs xn--fiq64b xn--fjq720a xn--flw351e xn--fzys8d69uvgm xn--g2xx48c xn--gckr3f0f xn--gk3at1e xn--hxt814e xn--i1b6b1a6a2e xn--imr513n xn--io0a7i xn--j1aef xn--jlq480n2rg xn--jvr189m xn--kcrx77d1x4a xn--kput3i xn--mgba3a3ejt xn--mgba7c0bbn0a xn--mgbab2bd xn--mgbca7dzdo xn--mgbi4ecexp xn--mgbt3dhd xn--mk1bu44c xn--mxtq1m xn--ngbc5azd xn--ngbe9e0a xn--ngbrx xn--nqv7f xn--nqv7fs00ema xn--nyqy26a xn--otu796d xn--p1acf xn--pssy2u xn--q9jyb4c xn--qcka1pmc xn--rhqv96g xn--rovu88b xn--ses554g xn--t60b56a xn--tckwe xn--tiq49xqyj xn--unup4y xn--vermgensberater-ctb xn--vermgensberatung-pwb xn--vhquv xn--vuq861b xn--w4r85el8fhu5dnra xn--w4rs40l xn--xhq521b xn--zfr164b xyz yachts yahoo yamaxun yandex yodobashi yoga yokohama you youtube yun zappos zara zero zip zone zuerich".split(' '));
  function getRegistrableGuess(hostname) {
    const clean = String(hostname || '').toLowerCase().replace(/^www\./, '').replace(/\.$/, '');
    if (/^\d{1,3}(\.\d{1,3}){3}$/.test(clean) || clean.includes(':')) return clean;
    const labels = clean.split('.').filter(Boolean);
    let suffixSize = 1;
    for (let i = 0; i < labels.length; i++) {
      const tail = labels.slice(i).join('.');
      if (PUBLIC_SUFFIX_RULES.has('!' + tail)) { suffixSize = labels.length - i - 1; break; }
      if (PUBLIC_SUFFIX_RULES.has(tail) || (i + 1 < labels.length && PUBLIC_SUFFIX_RULES.has('*.' + labels.slice(i + 1).join('.')))) {
        suffixSize = Math.max(suffixSize, labels.length - i);
      }
    }
    return labels.slice(-Math.min(labels.length, suffixSize + 1)).join('.');
  }
  // END GENERATED PSL

  function isSubdomainOrSame(host, domain) {
    host = String(host || '').replace(/^www\./, '').toLowerCase();
    domain = String(domain || '').replace(/^www\./, '').toLowerCase();
    return host === domain || host.endsWith('.' + domain);
  }

  function officialProfilesForHost(hostname) {
    return BRAND_PROFILES.filter(profile => profile.officialDomains.some(d => isSubdomainOrSame(hostname, d)));
  }

  function levenshtein(a, b) {
    a = String(a || ''); b = String(b || '');
    const dp = Array.from({ length: a.length + 1 }, () => Array(b.length + 1).fill(0));
    for (let i = 0; i <= a.length; i++) dp[i][0] = i;
    for (let j = 0; j <= b.length; j++) dp[0][j] = j;
    for (let i = 1; i <= a.length; i++) {
      for (let j = 1; j <= b.length; j++) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost);
      }
    }
    return dp[a.length][b.length];
  }

  function skeleton(str) {
    return String(str || '').toLowerCase()
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[0οо]/g, 'o')
      .replace(/[1!|ιіӏ]/g, 'l')
      .replace(/[3]/g, 'e')
      .replace(/[4@]/g, 'a')
      .replace(/[5$]/g, 's')
      .replace(/[7]/g, 't')
      .replace(/[8]/g, 'b')
      .replace(/[9]/g, 'g')
      .replace(/rn/g, 'm')
      .replace(/vv/g, 'w')
      .replace(/[^a-z0-9]/g, '');
  }

  function shannonEntropy(str) {
    str = String(str || '');
    if (!str) return 0;
    const counts = {};
    for (const ch of str) counts[ch] = (counts[ch] || 0) + 1;
    let entropy = 0;
    for (const ch in counts) {
      const p = counts[ch] / str.length;
      entropy -= p * Math.log2(p);
    }
    return entropy;
  }

  function hasPrivateIp(hostname) {
    const m = String(hostname).match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
    if (!m) return false;
    const [a, b] = m.slice(1).map(Number);
    return a === 10 || a === 127 || (a === 192 && b === 168) || (a === 172 && b >= 16 && b <= 31);
  }

  function addReason(reasons, points, label, detail = '', category = 'general') {
    reasons.push({ points, label, detail, category });
  }

  function findKeywordHits(text, list, limit = 8) {
    const lower = String(text || '').toLowerCase();
    const hits = [];
    for (const raw of list) {
      const key = String(raw || '').toLowerCase();
      if (!key || hits.includes(raw)) continue;
      if (lower.includes(key)) hits.push(raw);
      if (hits.length >= limit) break;
    }
    return hits;
  }

  function classify(score) {
    if (score >= 80) return { level: 'critical', text: 'อันตรายมาก' };
    if (score >= 60) return { level: 'high', text: 'เสี่ยงสูง' };
    if (score >= 31) return { level: 'medium', text: 'น่าสงสัย' };
    return { level: 'low', text: 'ปลอดภัย' };
  }

  function deriveThreatTypes(reasons) {
    const cats = new Set((reasons || []).filter(r => r.points > 0).map(r => r.category));
    const out = [];
    if (cats.has('brand') || cats.has('visual-brand') || cats.has('credential') || cats.has('form') || cats.has('combo')) out.push('Phishing / ขโมยข้อมูล');
    if (cats.has('malware-content') || cats.has('download')) out.push('Malware / ไฟล์เสี่ยง');
    if (cats.has('scam-content') || cats.has('gambling-content') || cats.has('crypto-content')) out.push('Scam / Fraud');
    if (cats.has('adult-content') || cats.has('search-context')) out.push('SEO Spam / เนื้อหาอ่อนไหว');
    if (cats.has('redirect')) out.push('Redirect / ปลายทางไม่ชัดเจน');
    if (cats.has('transport')) out.push('No HTTPS');
    return out.length ? out.slice(0, 4) : ['ไม่พบกลุ่มความเสี่ยงสำคัญ'];
  }

  function findRedirectTargets(url, search) {
    const results = [];
    for (const [key, value] of url.searchParams.entries()) {
      const k = key.toLowerCase();
      const v = safeDecode(value);
      if (/^(url|u|redirect|redirect_uri|next|target|to|continue|return|returnurl|dest|destination)$/i.test(k) || /^https?:\/\//i.test(v)) {
        const nested = normalizeUrl(v);
        if (nested && nested.hostname && nested.hostname !== url.hostname) {
          results.push(`${key} → ${nested.hostname}`);
        }
      }
    }
    if (/https?%3a%2f%2f/i.test(search)) results.push('พบ URL ที่ถูก encode อยู่ใน query');
    return results;
  }

  function detectLinkTextMismatch(text, hostname) {
    const cleaned = String(text || '').replace(/\s+/g, ' ').trim();
    if (!cleaned) return null;
    const match = cleaned.match(/((?:https?:\/\/)?(?:www\.)?[a-z0-9.-]+\.[a-z]{2,})(?:\/\S*)?/i);
    if (!match) return null;
    const visible = normalizeUrl(match[1])?.hostname?.replace(/^www\./, '');
    const actual = String(hostname || '').replace(/^www\./, '');
    if (visible && actual && visible !== actual && !actual.endsWith('.' + visible) && !visible.endsWith('.' + actual)) {
      return `${visible} → ${actual}`;
    }
    return null;
  }

  function credentialQueryKeys(url, depth = 0) {
    const keys = [];
    for (const [key, value] of url.searchParams.entries()) {
      if (value.trim() && /^(?:password|passwd|pwd|otp|token|access_token|refresh_token|id_token|session|session_id|sessionid|auth|credential|pin|seed|seed_phrase|recovery_phrase|private[._-]?key)$/i.test(key)) keys.push(key);
      // Retain evidence in a real nested destination URL without matching a
      // credential word buried inside arbitrary tracking strings or key names.
      if (depth < 3 && /^https?:\/\//i.test(value)) {
        try { keys.push(...credentialQueryKeys(new URL(value), depth + 1)); } catch (_) {}
      }
    }
    return [...new Set(keys)];
  }

  function analyzeUrl(input, options = {}) {
    let url = normalizeUrl(input);
    const reasons = [];
    let score = 0;
    let localFileContextMode = false;

    if (!url) {
      return {
        input,
        url: String(input || ''),
        score: 100,
        level: 'high',
        levelText: 'เสี่ยงสูง',
        reasons: [{ points: 100, label: 'URL ไม่ถูกต้อง', detail: 'ระบบอ่านรูปแบบ URL ไม่ได้', category: 'parse' }],
        safe: false,
        summary: 'URL parse failed'
      };
    }

    if (!/^https?:$/.test(url.protocol)) {
      const hasPageContext = !!(
        options.pageHasPasswordForm ||
        Number(options.passwordFieldCount || 0) > 0 ||
        Number(options.otpFieldCount || 0) > 0 ||
        (Array.isArray(options.formIssues) && options.formIssues.length) ||
        options.pageText ||
        options.documentTitle
      );

      // For local classroom test pages opened as file://, continue scoring the
      // DOM/page context. This lets the extension demonstrate form protection
      // without hosting a real phishing site. Non-web pages without context stay safe.
      if (url.protocol === 'file:' && hasPageContext) {
        localFileContextMode = true;
        const virtualPath = String(url.pathname || '/').replace(/[^a-z0-9/_.,-]/gi, '-');
        url = new URL(`http://local-file-demo.invalid${virtualPath.startsWith('/') ? virtualPath : '/' + virtualPath}`);
      } else {
        return {
          input,
          url: url.href,
          hostname: url.hostname || url.protocol,
          domain: url.hostname || url.protocol,
          score: 0,
          level: 'low',
          levelText: 'ไม่ใช่หน้าเว็บปกติ',
          reasons: [{ points: 0, label: 'โปรโตคอลนี้ไม่ถูกตรวจแบบเว็บ', detail: url.protocol, category: 'protocol' }],
          safe: true,
          summary: 'Non-web URL'
        };
      }
    }

    const hrefRaw = url.href;
    const href = safeDecode(hrefRaw);
    const hostname = url.hostname.toLowerCase().replace(/\.$/, '');
    const pathname = safeDecode(url.pathname || '').toLowerCase();
    const search = safeDecode(url.search || '').toLowerCase();
    const fullLower = href.toLowerCase();
    const domainGuess = getRegistrableGuess(hostname);
    const domainLabel = domainGuess.split('.')[0] || hostname;
    const parts = hostname.split('.').filter(Boolean);
    const subdomainLevels = Math.max(0, hostname.replace(/^www\./, '').split('.').filter(Boolean).length - domainGuess.split('.').length);
    const tld = parts[parts.length - 1] || '';
    const officialProfiles = officialProfilesForHost(hostname);
    const isKnownOfficial = officialProfiles.length > 0;
    const positiveBeforeTrust = () => reasons.filter(r => r.points > 0).reduce((sum, r) => sum + r.points, 0);
    const searchContextRaw = String(options.searchContextText || options.resultText || '').replace(/\s+/g, ' ').trim().slice(0, 1200);
    const searchContextLower = searchContextRaw.toLowerCase();
    const isAdultOfficialDomain = ADULT_CONTENT_DOMAINS.some(d => isSubdomainOrSame(hostname, d));
    const looksLikeCmsUpload = CMS_UPLOAD_PATTERNS.some(p => (pathname + '/' + search).includes(p));
    const pageTextLower = String(options.pageText || '').toLowerCase().slice(0, 8000);
    const visibleContextLower = String(options.linkText || options.visibleText || '').toLowerCase().slice(0, 700);
    const combinedContextLower = [fullLower, searchContextLower, visibleContextLower, pageTextLower].filter(Boolean).join(' ');

    if (localFileContextMode) {
      addReason(reasons, 0, 'โหมดจำลองไฟล์ในเครื่อง', 'ใช้สำหรับทดสอบฟอร์ม/ข้อความโดยไม่เข้าเว็บจริง', 'protocol');
    }

    if (url.protocol !== 'https:') {
      score += 18;
      addReason(reasons, 18, 'ไม่ได้ใช้ HTTPS', 'เว็บล็อกอิน/ชำระเงินควรเข้ารหัสข้อมูล', 'transport');
    }

    if (isKnownOfficial) {
      score -= 25;
      addReason(reasons, -25, 'โดเมนอยู่ในรายการทางการของแบรนด์', officialProfiles.map(p => p.brand).join(', '), 'trust');
    }

    if (/^\d{1,3}(\.\d{1,3}){3}$/.test(hostname)) {
      score += 25;
      addReason(reasons, 25, 'ใช้ IP address แทนชื่อโดเมน', hostname, 'domain');
      if (!hasPrivateIp(hostname)) {
        score += 6;
        addReason(reasons, 6, 'เป็น public IP ที่ผู้ใช้จำได้ยาก', 'มักใช้หลอกให้ดูไม่ออกว่าเป็นเว็บใคร', 'domain');
      }
    }

    if (hasPrivateIp(hostname)) {
      score += 4;
      addReason(reasons, 4, 'เป็น private/local IP', 'อาจเป็นหน้าอุปกรณ์ภายในหรือเดโม ไม่ควรกรอกข้อมูลสำคัญหากไม่แน่ใจ', 'domain');
    }

    if (url.port && !['80', '443'].includes(url.port)) {
      score += 6;
      addReason(reasons, 6, 'ใช้พอร์ตที่ไม่ใช่มาตรฐาน', `:${url.port}`, 'domain');
    }

    if (hrefRaw.length > 120) {
      score += 14;
      addReason(reasons, 14, 'URL ยาวผิดปกติมาก', `${hrefRaw.length} ตัวอักษร`, 'url-shape');
    } else if (hrefRaw.length > 85) {
      score += 8;
      addReason(reasons, 8, 'URL ยาวกว่าปกติ', `${hrefRaw.length} ตัวอักษร`, 'url-shape');
    }

    if (hostname.length > 45) {
      score += 10;
      addReason(reasons, 10, 'ชื่อโฮสต์ยาวผิดปกติ', hostname, 'domain');
    }

    if (domainLabel.length > 24) {
      score += 8;
      addReason(reasons, 8, 'ชื่อโดเมนหลักยาวผิดปกติ', domainLabel, 'domain');
    }

    const longestLabel = parts.reduce((max, part) => part.length > max.length ? part : max, '');
    if (longestLabel.length > 32) {
      score += 8;
      addReason(reasons, 8, 'มี label ในโดเมนยาวผิดปกติ', longestLabel, 'domain');
    }

    const hyphenCount = (domainLabel.match(/-/g) || []).length;
    if (hyphenCount >= 3) {
      const points = Math.min(16, 6 + hyphenCount * 3);
      score += points;
      addReason(reasons, points, 'มีขีดกลางในชื่อโดเมนจำนวนมาก', `${hyphenCount} จุด`, 'domain');
    } else if (hyphenCount === 2) {
      score += 6;
      addReason(reasons, 6, 'มีขีดกลางในชื่อโดเมนหลายจุด', domainLabel, 'domain');
    }

    if (subdomainLevels >= 3) {
      score += 14;
      addReason(reasons, 14, 'มี subdomain ซ้อนหลายชั้นมาก', hostname, 'domain');
    } else if (subdomainLevels >= 2) {
      score += 9;
      addReason(reasons, 9, 'มี subdomain หลายชั้น', hostname, 'domain');
    }

    if (TLD_RISK.has(tld)) {
      score += 13;
      addReason(reasons, 13, 'นามสกุลโดเมนมีความเสี่ยงในบริบท phishing', `.${tld}`, 'domain');
    }

    if (hostname.includes('xn--')) {
      score += 24;
      addReason(reasons, 24, 'อาจใช้ตัวอักษรหลอกตาแบบ IDN/Punycode', hostname, 'homograph');
    }

    if (url.username || url.password) {
      score += 22;
      addReason(reasons, 22, 'URL มีเครื่องหมาย @ ในส่วน userinfo', 'อาจใช้ซ่อนปลายทางจริงหลังเครื่องหมาย @', 'url-shape');
    }

    if (/[\\]/.test(hrefRaw)) {
      score += 8;
      addReason(reasons, 8, 'URL มี backslash', 'อาจทำให้ผู้ใช้สับสนกับ path จริง', 'url-shape');
    }

    const encodedCount = (hrefRaw.match(/%[0-9a-f]{2}/gi) || []).length;
    if (encodedCount >= 8) {
      score += 10;
      addReason(reasons, 10, 'มีการ encode ตัวอักษรจำนวนมาก', `${encodedCount} จุด`, 'url-shape');
    }

    if ((hrefRaw.match(/https?:\/\//gi) || []).length > 1) {
      score += 12;
      addReason(reasons, 12, 'มี URL ซ้อนอยู่ใน URL', 'มักพบในลิงก์ redirect หลอกปลายทาง', 'redirect');
    }

    const redirectTargets = findRedirectTargets(url, search);
    if (redirectTargets.length) {
      score += 18;
      addReason(reasons, 18, 'พบพารามิเตอร์ redirect ไปโดเมนอื่น', redirectTargets.slice(0, 3).join(', '), 'redirect');
    }

    const pathDepth = pathname.split('/').filter(Boolean).length;
    if (pathDepth >= 6) {
      score += 8;
      addReason(reasons, 8, 'path ลึกหลายชั้น', `${pathDepth} ชั้น`, 'url-shape');
    }

    if (url.searchParams && Array.from(url.searchParams).length >= 7) {
      score += 8;
      addReason(reasons, 8, 'มี query parameters จำนวนมาก', `${Array.from(url.searchParams).length} รายการ`, 'url-shape');
    }

    const secretQueryKeys = credentialQueryKeys(url);
    if (secretQueryKeys.length) {
      score += 24;
      addReason(reasons, 24, 'URL อาจส่งข้อมูลลับผ่าน query string', 'พบชื่อพารามิเตอร์ข้อมูลสำคัญ: ' + secretQueryKeys.slice(0, 5).join(', '), 'credential');
    }

    if (/[A-Za-z0-9+/=_-]{32,}/.test(search)) {
      score += 8;
      // Opaque strings also occur in ordinary tracking IDs (e.g. fbclid).
      // Length alone cannot establish that credentials were requested/sent.
      addReason(reasons, 8, 'พบข้อความยาวในพารามิเตอร์ URL', 'อาจเป็นรหัสติดตามลิงก์ ความยาวเพียงอย่างเดียวไม่ยืนยันว่ามีข้อมูลลับ', 'url-shape');
    }

    const lowerPath = pathname.toLowerCase();
    const suspiciousFile = SUSPICIOUS_FILE_EXTENSIONS.find(ext => lowerPath.endsWith(ext) || lowerPath.includes(ext + '?'));
    if (suspiciousFile) {
      score += 24;
      addReason(reasons, 24, 'ลิงก์ไปยังไฟล์ที่อาจเป็นอันตราย', suspiciousFile, 'download');
    }
    const archiveFile = ARCHIVE_EXTENSIONS.find(ext => lowerPath.endsWith(ext) || lowerPath.includes(ext + '?'));
    if (archiveFile) {
      score += 7;
      addReason(reasons, 7, 'ลิงก์ดาวน์โหลดไฟล์บีบอัด', archiveFile, 'download');
    }

    if (searchContextRaw) {
      const adultHits = ADULT_SEO_KEYWORDS.filter(k => searchContextLower.includes(k.toLowerCase()));
      const contextMentionsAdultBrand = ADULT_CONTENT_DOMAINS
        .map(d => d.replace(/\.com$/i, ''))
        .filter(name => searchContextLower.includes(name));
      const isDocLike = /\.(pdf|docx?|xlsx?|pptx?)(?:$|[?#/])/i.test(pathname) || /\bpdf\b/i.test(searchContextLower);
      const isPublicOrAcademicHost = /\.(edu|org|gov|ac\.[a-z]{2}|go\.[a-z]{2}|or\.[a-z]{2})$/i.test(hostname);

      if (adultHits.length && !isAdultOfficialDomain) {
        score += 18;
        addReason(reasons, 18, 'ผลค้นหามีคำกลุ่ม Adult/SEO spam แต่ปลายทางไม่ใช่โดเมนเนื้อหานั้นโดยตรง', adultHits.slice(0, 5).join(', '), 'search-context');
      }
      if (adultHits.length && isPublicOrAcademicHost && !isAdultOfficialDomain) {
        score += 18;
        addReason(reasons, 18, 'โดเมนสาธารณะ/องค์กร/การศึกษาถูกใช้กับหัวข้อผิดบริบท', hostname, 'search-context');
      }
      if (adultHits.length && looksLikeCmsUpload) {
        score += 14;
        addReason(reasons, 14, 'path คล้ายไฟล์อัปโหลดจาก CMS หรือโฟลเดอร์ชั่วคราว', pathname.slice(0, 120), 'search-context');
      }
      if (adultHits.length && isDocLike && !isAdultOfficialDomain) {
        score += 14;
        addReason(reasons, 14, 'ลิงก์เอกสาร/PDF ในผลค้นหาที่มีคำเสี่ยง', 'อาจเป็น SEO spam หรือไฟล์ที่ถูกฝังในเว็บที่ถูกโจมตี', 'search-context');
      }
      if (contextMentionsAdultBrand.length && !isAdultOfficialDomain) {
        score += 16;
        addReason(reasons, 16, 'ข้อความผลค้นหาอ้างเว็บ Adult ชื่อดัง แต่ URL ปลายทางเป็นคนละโดเมน', contextMentionsAdultBrand.slice(0, 4).join(', '), 'search-context');
      }
    }

    // Broader harmful/risky content detection beyond phishing.
    const malwareContentHits = findKeywordHits(combinedContextLower, MALWARE_CONTENT_KEYWORDS);
    if (malwareContentHits.length) {
      const points = Math.min(28, 12 + malwareContentHits.length * 4);
      score += points;
      addReason(reasons, points, 'พบคำหรือบริบทที่เกี่ยวกับมัลแวร์/ไฟล์เสี่ยง', malwareContentHits.slice(0, 6).join(', '), 'malware-content');
    }

    const scamContentHits = findKeywordHits(combinedContextLower, SCAM_CONTENT_KEYWORDS);
    if (scamContentHits.length) {
      const points = Math.min(24, 10 + scamContentHits.length * 4);
      score += points;
      addReason(reasons, points, 'พบคำที่มักใช้ในเว็บหลอกลวงหรือกลโกงออนไลน์', scamContentHits.slice(0, 6).join(', '), 'scam-content');
    }

    const gamblingHits = findKeywordHits(combinedContextLower, GAMBLING_CONTENT_KEYWORDS);
    if (gamblingHits.length) {
      const points = Math.min(22, 10 + gamblingHits.length * 4);
      score += points;
      addReason(reasons, points, 'พบเนื้อหาเว็บพนัน/การพนันออนไลน์', gamblingHits.slice(0, 6).join(', '), 'gambling-content');
    }

    const adultContextHits = findKeywordHits([fullLower, searchContextLower, visibleContextLower].join(' '), SENSITIVE_ADULT_CONTEXT_KEYWORDS);
    if (adultContextHits.length && !isAdultOfficialDomain && !searchContextRaw) {
      const points = Math.min(20, 8 + adultContextHits.length * 3);
      score += points;
      addReason(reasons, points, 'พบคำกลุ่มเนื้อหา Adult/Spam ใน URL หรือข้อความลิงก์', adultContextHits.slice(0, 6).join(', '), 'adult-content');
    }

    if (/allow notifications|enable notifications|click allow|กดอนุญาต|เปิดการแจ้งเตือน/i.test(combinedContextLower) &&
        /virus|download|player|verify|captcha|malware|ไวรัส|ดาวน์โหลด|ยืนยัน/i.test(combinedContextLower)) {
      score += 16;
      addReason(reasons, 16, 'พบข้อความหลอกให้กด Allow/Notification', 'มักพบในเว็บหลอกโหลดไฟล์หรือโฆษณาอันตราย', 'malware-content');
    }

    if (/seed phrase|recovery phrase|private key|wallet connect|airdrop|claim token|กระเป๋าเงิน|คริปโต|โทเคน/i.test(combinedContextLower) &&
        /claim|verify|connect|bonus|free|รับสิทธิ์|แจก|ยืนยัน|ล็อกอิน/i.test(combinedContextLower)) {
      score += 18;
      addReason(reasons, 18, 'พบบริบทหลอกลวงเกี่ยวกับคริปโต/กระเป๋าเงิน', 'ควรระวังการขอ seed phrase หรือการเชื่อมกระเป๋าเงิน', 'crypto-content');
    }

    if (SHORTENERS.some(d => isSubdomainOrSame(hostname, d))) {
      score += 15;
      addReason(reasons, 15, 'เป็นลิงก์ย่อ', 'ควรตรวจปลายทางจริงก่อนเปิด', 'redirect');
    }

    const hosting = FREE_HOSTING_OR_DDNS.find(d => isSubdomainOrSame(hostname, d));
    if (hosting) {
      score += 9;
      addReason(reasons, 9, 'ใช้ free hosting หรือ dynamic DNS', hosting, 'hosting');
    }

    const labelSkeleton = skeleton(domainLabel);
    const hostTokens = hostname.split(/[.-]/).filter(Boolean).map(skeleton).filter(Boolean).filter(t => !IGNORE_BRAND_TOKEN_MATCH.has(t));
    const entropy = shannonEntropy(domainLabel.replace(/-/g, ''));
    const digitCount = (domainLabel.match(/\d/g) || []).length;
    const digitRatio = domainLabel.length ? digitCount / domainLabel.length : 0;
    const vowelRatio = domainLabel.length ? ((domainLabel.match(/[aeiou]/gi) || []).length / domainLabel.length) : 1;

    if (domainLabel.length >= 13 && entropy >= 3.55 && vowelRatio < 0.28 && !isKnownOfficial) {
      score += 11;
      addReason(reasons, 11, 'ชื่อโดเมนดูสุ่มผิดปกติ', `entropy ${entropy.toFixed(2)}`, 'domain');
    }

    if (digitRatio >= 0.28 && domainLabel.length >= 8) {
      score += 8;
      addReason(reasons, 8, 'ชื่อโดเมนมีตัวเลขปนมาก', `${Math.round(digitRatio * 100)}% เป็นตัวเลข`, 'domain');
    }

    const keywordHits = keywordMatches(fullLower, SUSPICIOUS_KEYWORDS);
    if (keywordHits.length) {
      const points = Math.min(24, keywordHits.length * 4 + 2);
      score += points;
      addReason(reasons, points, 'พบคำที่มักใช้หลอกให้ล็อกอิน/ยืนยันตัวตน', keywordHits.slice(0, 8).join(', '), 'keyword');
      if (keywordHits.length >= 6) {
        score += 8;
        addReason(reasons, 8, 'พบ keyword เสี่ยงเป็นกลุ่มจำนวนมาก', `${keywordHits.length} คำ`, 'keyword');
      }
    }

    const credentialHits = keywordMatches(fullLower, CREDENTIAL_KEYWORDS);
    if (credentialHits.length) {
      const points = Math.min(18, credentialHits.length * 6);
      score += points;
      addReason(reasons, points, 'พบคำเกี่ยวกับข้อมูลลับ/รหัสผ่าน', credentialHits.slice(0, 5).join(', '), 'credential');
    }

    const brandFindings = [];
    for (const profile of BRAND_PROFILES) {
      const names = [profile.brand, ...profile.aliases].filter(Boolean).filter(name => skeleton(name).length >= 3);
      const official = profile.officialDomains.some(d => isSubdomainOrSame(hostname, d));
      // A brand mention in a path/article is not evidence of impersonation.
      const hostContains = names.find(name => hostTokens.includes(skeleton(name)));
      let lookalike = null;
      for (const name of names) {
        const nameSkel = skeleton(name);
        const maxDistance = nameSkel.length >= 8 ? 2 : nameSkel.length >= 5 ? 1 : 0;
        const dist = levenshtein(labelSkeleton, nameSkel);
        const tokenClose = hostTokens.some(t => {
          if (t.length < Math.max(3, nameSkel.length - 2) || t.length > nameSkel.length + 4) return false;
          const d = levenshtein(t, nameSkel);
          return maxDistance > 0 && d > 0 && d <= maxDistance && t.length >= 5;
        });
        const close = maxDistance > 0 && labelSkeleton.length >= 5 && dist > 0 && dist <= maxDistance;
        const embedded = labelSkeleton.includes(nameSkel) && labelSkeleton !== nameSkel;
        const tokenEmbedded = hostTokens.some(t => t.includes(nameSkel) && t !== nameSkel);
        const confusable = labelSkeleton === nameSkel && domainLabel.toLowerCase() !== name.toLowerCase();
        if (close || tokenClose || confusable || ((embedded || tokenEmbedded) && /login|secure|verify|support|account|update|help|pay|wallet/.test(labelSkeleton + hostTokens.join('')))) {
          lookalike = name;
          break;
        }
      }
      if (!official && (hostContains || lookalike)) {
        brandFindings.push({ brand: profile.brand, matched: hostContains || lookalike, lookalike: !!lookalike });
      }
    }

    if (brandFindings.length) {
      const main = brandFindings[0];
      const points = main.lookalike ? 30 : main.inPath ? 16 : 24;
      score += points;
      addReason(reasons, points, 'โดเมน/URL มีลักษณะเลียนแบบแบรนด์จริง', `${hostname} อ้างถึง ${main.brand}`, 'brand');
    }

    if (brandFindings.length && (keywordHits.some(k => /login|verify|account|secure|update|support|kyc|payment|wallet|ล็อกอิน|ยืนยัน/.test(k.toLowerCase())) || credentialHits.length)) {
      score += 14;
      addReason(reasons, 14, 'พบชื่อแบรนด์ร่วมกับคำเกี่ยวกับบัญชีหรือรหัสผ่าน', brandFindings.map(b => b.brand).slice(0, 3).join(', '), 'brand');
    }

    if ((options.linkText || options.visibleText) && !options.ignoreLinkText) {
      const text = String(options.linkText || options.visibleText || '').slice(0, 300);
      const mismatch = detectLinkTextMismatch(text, hostname);
      if (mismatch) {
        score += 24;
        addReason(reasons, 24, 'ข้อความลิงก์ไม่ตรงกับปลายทางจริง', mismatch, 'link-context');
      }
      const textLower = text.toLowerCase();
      const textPressure = PRESSURE_WORDS.filter(w => textLower.includes(w.toLowerCase()));
      if (textPressure.length) {
        score += 6;
        addReason(reasons, 6, 'ข้อความลิงก์มีคำเร่งเร้า/กดดัน', textPressure.slice(0, 3).join(', '), 'link-context');
      }
    }

    if (options.opensNewTabNoNoopener) {
      score += 3;
      addReason(reasons, 3, 'ลิงก์เปิดสิทธิ์ให้แท็บใหม่เข้าถึงแท็บต้นทาง', 'มีความเสี่ยง tabnabbing ระดับต่ำ', 'link-context');
    }

    const formIssues = Array.isArray(options.formIssues) ? options.formIssues : [];
    for (const issue of formIssues.slice(0, 6)) {
      const points = Number(issue.points || 0);
      if (!points) continue;
      score += points;
      addReason(reasons, points, issue.label || 'พบความเสี่ยงในฟอร์ม', issue.detail || '', 'form');
    }

    if (options.pageHasPasswordForm) {
      const points = isKnownOfficial && url.protocol === 'https:' ? 3 : 12;
      score += points;
      addReason(reasons, points, 'หน้านี้มีช่องรหัสผ่าน', 'เพิ่มความเสี่ยงหากโดเมนไม่น่าเชื่อถือ', 'form');
    }

    if (options.passwordFieldCount > 1) {
      score += 5;
      addReason(reasons, 5, 'มีช่องรหัสผ่านหลายช่อง', `${options.passwordFieldCount} ช่อง`, 'form');
    }

    if (options.otpFieldCount > 0) {
      score += 10;
      addReason(reasons, 10, 'มีช่องกรอก OTP/Token', `${options.otpFieldCount} ช่อง`, 'form');
    }

    if (options.documentTitle && !isKnownOfficial) {
      const title = String(options.documentTitle).toLowerCase();
      const titleBrand = KNOWN_BRANDS.find(b => title.includes(b.toLowerCase()));
      const titleCred = CREDENTIAL_KEYWORDS.find(k => title.includes(k.toLowerCase()));
      if (titleBrand && (titleCred || keywordHits.length)) {
        score += 10;
        addReason(reasons, 10, 'ชื่อหน้าเว็บอ้างถึงแบรนด์/บัญชี แต่โดเมนไม่ใช่ทางการ', options.documentTitle.slice(0, 80), 'page-context');
      }
    }

    if (options.pageText) {
      const text = String(options.pageText).slice(0, 8000).toLowerCase();
      const pressureHits = PRESSURE_WORDS.filter(w => text.includes(w.toLowerCase()));
      if (pressureHits.length) {
        score += 8;
        addReason(reasons, 8, 'พบข้อความเร่งให้รีบทำรายการ', pressureHits.slice(0, 5).join(', '), 'page-context');
      }
      if (/(seed phrase|recovery phrase|private key|รหัส otp|กรอก otp|รหัสผ่าน|ข้อมูลบัตร|หมายเลขบัตร|cvv)/i.test(text)) {
        score += 12;
        addReason(reasons, 12, 'หน้าเว็บขอข้อมูลสำคัญ', 'พบคำเกี่ยวกับ OTP/รหัสผ่าน/บัตร/seed phrase', 'page-context');
      }
    }


    const visualFindings = Array.isArray(options.visualFindings) ? options.visualFindings : [];
    for (const finding of visualFindings.slice(0, 4)) {
      const points = Math.max(10, Math.min(34, Number(finding.points || 0) || 20));
      if (!points) continue;
      score += points;
      const signalText = Array.isArray(finding.signals) && finding.signals.length ? ' | สัญญาณ: ' + finding.signals.slice(0, 4).join(', ') : '';
      addReason(
        reasons,
        points,
        'หน้าตาเว็บเลียนแบบแบรนด์แต่โดเมนไม่ใช่ทางการ',
        (finding.detail || ('อ้างถึง ' + (finding.brand || 'แบรนด์จริง'))) + signalText,
        'visual-brand'
      );
    }

    // Combination rules: phishing is usually a cluster of weak signals.
    const categories = new Set(reasons.filter(r => r.points > 0).map(r => r.category));
    if (categories.has('brand') && categories.has('credential')) {
      score += 10;
      addReason(reasons, 10, 'สัญญาณร่วม: เลียนแบบแบรนด์ + ขอข้อมูลลับ', 'ความเสี่ยงเพิ่มขึ้นเมื่อสองเงื่อนไขเกิดพร้อมกัน', 'combo');
    }
    if (categories.has('visual-brand') && (categories.has('form') || categories.has('credential'))) {
      score += 12;
      addReason(reasons, 12, 'สัญญาณร่วม: หน้าตาคล้ายแบรนด์จริง + ขอข้อมูลสำคัญ', 'เข้าข่าย visual phishing เพราะผู้ใช้อาจเชื่อจากหน้าตาเว็บมากกว่า URL', 'combo');
    }
    if (categories.has('brand') && categories.has('transport')) {
      score += 8;
      addReason(reasons, 8, 'สัญญาณร่วม: อ้างแบรนด์แต่ไม่ใช้ HTTPS', 'ผิดปกติสำหรับบริการจริง', 'combo');
    }
    if (categories.has('form') && (categories.has('brand') || categories.has('keyword')) && !isKnownOfficial) {
      score += 10;
      addReason(reasons, 10, 'สัญญาณร่วม: มีฟอร์มล็อกอินบนเว็บที่น่าสงสัย', 'ควรบล็อกก่อนผู้ใช้กรอกข้อมูล', 'combo');
    }
    if (categories.has('redirect') && categories.has('keyword')) {
      score += 6;
      addReason(reasons, 6, 'สัญญาณร่วม: redirect + คำชวนให้ยืนยันบัญชี', 'มักใช้พาผู้ใช้ไปปลายทางหลอก', 'combo');
    }
    if (categories.has('download') && categories.has('keyword')) {
      score += 8;
      addReason(reasons, 8, 'สัญญาณร่วม: ไฟล์ดาวน์โหลด + คำหลอกให้ทำรายการ', 'ควรเตือนก่อนดาวน์โหลดไฟล์', 'combo');
    }

    if (categories.has('search-context') && (categories.has('url-shape') || categories.has('download'))) {
      score += 8;
      addReason(reasons, 8, 'สัญญาณร่วม: ผลค้นหาผิดบริบท + รูปแบบ URL/ไฟล์น่าสงสัย', 'เข้าข่าย SEO spam หรือเว็บที่ถูกฝังลิงก์แปลกปลอม', 'combo');
    }

    if ((categories.has('malware-content') || categories.has('adult-content') || categories.has('gambling-content') || categories.has('scam-content') || categories.has('crypto-content')) &&
        (categories.has('redirect') || categories.has('url-shape') || categories.has('download'))) {
      score += 9;
      addReason(reasons, 9, 'สัญญาณร่วม: เนื้อหาเสี่ยง + รูปแบบลิงก์ผิดปกติ', 'ไม่ใช่ phishing เสมอไป แต่อาจเป็นเว็บหลอก โฆษณาอันตราย หรือไฟล์เสี่ยง', 'combo');
    }

    if (url.protocol === 'https:' && positiveBeforeTrust() === 0) {
      score -= 8;
      addReason(reasons, -8, 'ไม่พบสัญญาณเสี่ยงชัดเจน', 'URL เป็น HTTPS และรูปแบบปกติ', 'trust');
    }

    // Trust cap for known official HTTPS domains unless there are form/action or credential anomalies.
    const criticalOnOfficial = reasons.some(r => r.points > 0 && ['form', 'credential', 'redirect', 'download'].includes(r.category));
    if (isKnownOfficial && url.protocol === 'https:' && !criticalOnOfficial) {
      score = Math.min(score, 18);
    } else if (isKnownOfficial && url.protocol === 'https:') {
      score = Math.min(score, 42);
    }

    score = Math.max(0, Math.min(100, Math.round(score)));
    const c = classify(score);
    const sortedReasons = reasons
      .sort((a, b) => Math.abs(b.points) - Math.abs(a.points))
      .slice(0, 12);

    return {
      input,
      url: hrefRaw,
      hostname,
      domain: domainGuess,
      score,
      level: c.level,
      levelText: c.text,
      reasons: sortedReasons,
      threatTypes: deriveThreatTypes(sortedReasons),
      safe: score < 31,
      summary: `${c.text} (${score}/100)`,
      features: {
        urlLength: hrefRaw.length,
        hostLength: hostname.length,
        domain: domainGuess,
        tld,
        subdomainLevels,
        entropy: Number(entropy.toFixed(2)),
        keywordHits: keywordHits.slice(0, 10),
        credentialHits: credentialHits.slice(0, 10),
        officialBrand: officialProfiles.map(p => p.brand)
      }
    };
  }

  function badgeText(score) {
    if (score >= 80) return '!!';
    if (score >= 60) return 'HIGH';
    if (score >= 31) return 'WARN';
    return '✓';
  }

  const api = { analyzeUrl, classify, badgeText, KNOWN_BRANDS, SUSPICIOUS_KEYWORDS, BRAND_PROFILES };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  global.PhishRadarAnalyzer = api;
})(typeof globalThis !== 'undefined' ? globalThis : window);
