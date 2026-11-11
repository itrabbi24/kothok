import Demo from "./demo";
import ReleaseInfo from "./release-info";
import ThemeSwitch from "./theme-switch";

const REPO = "https://github.com/itrabbi24/kothok";
const DOWNLOAD = `${REPO}/releases/latest/download/Kothok-portable.zip`;

const features = [
  { icon: "🔒", title: "১০০% অফলাইন", text: "ইন্টারনেট, ক্লাউড বা API কিছুই লাগে না। আপনার ভয়েস কখনো পিসির বাইরে যায় না।" },
  { icon: "🇧🇩", title: "বাংলা + English একসাথে", text: "\"আমি আজকে I want to make a coffee\" — যেভাবে কথা বলেন, সেভাবেই লেখা।" },
  { icon: "⌨️", title: "যেকোনো অ্যাপে", text: "Word, Chrome, Facebook, WhatsApp, VS Code — কার্সর যেখানে, লেখা সেখানে।" },
  { icon: "📦", title: "ইনস্টল লাগে না", text: "Portable — zip খুলে চালান। পেনড্রাইভে করে অন্য পিসিতেও নিয়ে যেতে পারবেন।" },
  { icon: "🎚️", title: "লাইভ popup, যেখানে চান", text: "কথা বলার সময় সাউন্ড বার নড়ে। popup-টা নিচে মাঝখানে, ঘড়ির উপরে, বাম কোণে বা উপরে — যেখানে খুশি রাখুন।" },
  { icon: "📝", title: "নিজের শব্দ তালিকা", text: "নাম বা যে শব্দ বারবার ভুল আসে, \"Word fixes\"-এ একবার লিখে দিন (ভুল = সঠিক) — এরপর থেকে নিজে থেকেই ঠিক হয়ে যাবে।" },
  { icon: "⚡", title: "সবসময় রেডি", text: "পিসি চালু, sleep থেকে ফেরা বা লক খোলার পরেও শর্টকাট সাথে সাথে কাজ করে; মাইক বদলালেও নিজে খুঁজে নেয়।" },
  { icon: "🌗", title: "লাইট / ডার্ক থিম", text: "লাইট, ডার্ক, অথবা Windows-এর থিমের সাথে মিলিয়ে — যেটা চোখে আরাম।" },
  { icon: "🔄", title: "নিজে থেকে আপডেট", text: "নতুন ভার্সন এলে ব্যাকগ্রাউন্ডে চুপচাপ আপডেট হয়ে যায়, আপনার সেটিংস ঠিক থাকে।" },
  { icon: "💚", title: "ফ্রি ও ওপেন সোর্স", text: "MIT লাইসেন্স। কোড GitHub-এ খোলা — দেখুন, শিখুন, অবদান রাখুন।" },
];

const steps = [
  { n: "১", title: "ডাউনলোড করে unzip করুন", text: "যেকোনো ফোল্ডারে, যেমন D:\\Kothok" },
  { n: "২", title: "Kothok.exe চালান", text: "অ্যাপটা ঘড়ির পাশে system tray-তে বসে থাকবে" },
  { n: "৩", title: "Alt+R চেপে ধরে কথা বলুন", text: "ছেড়ে দিলেই লেখা বসে যাবে" },
];

const faqs = [
  { q: "সত্যিই কি ইন্টারনেট লাগে না?", a: "না। ভয়েস চেনার মডেল আপনার পিসিতেই চলে। শুধু নতুন ভার্সন আছে কিনা দেখতে অ্যাপ GitHub-এ একবার চেক করে, আর সেটাও tray মেনু থেকে বন্ধ করা যায়।" },
  { q: "Windows \"protected your PC\" দেখাচ্ছে, কী করব?", a: "exe-টা code-signed না বলে SmartScreen এই সতর্কবার্তা দেখায়। More info → Run anyway চাপুন। পুরো সোর্স কোড GitHub-এ আছে।" },
  { q: "English শব্দ বাংলা অক্ষরে আসছে কেন?", a: "বাক্যের মাঝখানে English বললে, English অংশের আগে-পরে একটু থামুন। তাহলে সেটা English অক্ষরে লেখা হবে।" },
  { q: "শর্টকাট বদলানো যায়?", a: "হ্যাঁ। সেটিংসে Change shortcut চেপে নিজের পছন্দের কী-কম্বিনেশন দিন। চেপে ধরে বলা বা একবার চেপে শুরু/শেষ — দুই মোডই আছে।" },
  { q: "কোন পিসিতে চলবে?", a: "Windows 10/11 (64-bit), ৪ GB+ RAM আর একটা মাইক্রোফোন। প্রায় ৪০০ MB জায়গা লাগে।" },
];

export default function Home() {
  return (
    <>
      <header className="nav">
        <div className="wrap nav-inner">
          <a href="#" className="brand">
            <img src="/logo.png" alt="" width="34" height="34" />
            <span className="bn">কথক</span>
            <span className="en">Kothok</span>
          </a>
          <div className="nav-right">
          <nav>
            <a href="#features">বৈশিষ্ট্য</a>
            <a href="#how">ব্যবহার</a>
            <a href="#faq">প্রশ্নোত্তর</a>
            <a href={REPO} className="gh">GitHub</a>
          </nav>
          <ThemeSwitch />
          </div>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="wrap hero-grid">
            <div>
              <p className="pill">Windows 10 / 11 · ফ্রি · ওপেন সোর্স</p>
              <h1>
                বলুন, <span className="accent">লেখা হয়ে যাক</span>
              </h1>
              <p className="lead">
                কথক একটা অফলাইন বাংলা + English ভয়েস টাইপিং অ্যাপ। যেকোনো অ্যাপে শর্টকাট চেপে কথা বলুন — লেখা ঠিক
                কার্সরের জায়গায় বসে যাবে। কোনো ইন্টারনেট বা অ্যাকাউন্ট লাগে না।
              </p>
              <div className="cta">
                <a className="btn primary" href={DOWNLOAD}>
                  ⬇ ফ্রি ডাউনলোড
                </a>
                <a className="btn ghost" href={REPO}>
                  সোর্স কোড দেখুন
                </a>
              </div>
              <ReleaseInfo />
            </div>
            <Demo />
          </div>
        </section>

        <section id="features" className="section">
          <div className="wrap">
            <h2>কেন কথক?</h2>
            <div className="grid3">
              {features.map((f) => (
                <div className="card" key={f.title}>
                  <div className="icon">{f.icon}</div>
                  <h3>{f.title}</h3>
                  <p>{f.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="how" className="section alt">
          <div className="wrap how-grid">
            <div>
              <h2>তিন ধাপে শুরু</h2>
              <ol className="steps">
                {steps.map((s) => (
                  <li key={s.n}>
                    <span className="num">{s.n}</span>
                    <div>
                      <h3>{s.title}</h3>
                      <p>{s.text}</p>
                    </div>
                  </li>
                ))}
              </ol>
              <p className="muted small">
                সেটিংস থেকে শর্টকাট, মোড, মাইক্রোফোন, ইঞ্জিন (বাংলা + English / শুধু বাংলা) থিম (লাইট / ডার্ক / ডিভাইস) আর popup-এর জায়গা সব বদলানো যায়।
              </p>
            </div>
            <figure className="shot">
              <img className="only-light" src="/screenshot-light.png" alt="Kothok-এর সেটিংস উইন্ডো" width="860" height="660" />
              <img className="only-dark" src="/screenshot-dark.png" alt="Kothok-এর সেটিংস উইন্ডো (ডার্ক থিম)" width="860" height="660" />
              <figcaption>কথক-এর সেটিংস উইন্ডো</figcaption>
            </figure>
          </div>
        </section>

        <section className="section">
          <div className="wrap tray">
            <h2>Tray আইকন দেখে বুঝুন অ্যাপ কী করছে</h2>
            <div className="states">
              <div><img src="/states/idle.png" alt="" width="64" height="64" /><span>প্রস্তুত</span></div>
              <div><img src="/states/rec.png" alt="" width="64" height="64" /><span>শুনছে</span></div>
              <div><img src="/states/busy.png" alt="" width="64" height="64" /><span>লিখছে</span></div>
              <div><img src="/states/error.png" alt="" width="64" height="64" /><span>সমস্যা</span></div>
            </div>
          </div>
        </section>

        <section id="faq" className="section alt">
          <div className="wrap narrow">
            <h2>প্রশ্নোত্তর</h2>
            {faqs.map((f) => (
              <details key={f.q}>
                <summary>{f.q}</summary>
                <p>{f.a}</p>
              </details>
            ))}
          </div>
        </section>

        <section id="video" className="section">
          <div className="wrap narrow center">
            <h2>দেখুন কীভাবে কাজ করে</h2>
            <div className="video">
              <iframe
                src="https://www.youtube-nocookie.com/embed/Hz5dy29OMLA?rel=0"
                title="কথক — ভয়েস টাইপিং ডেমো"
                loading="lazy"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                allowFullScreen
              />
            </div>
            <p className="muted small">
              <a href="https://youtube.com/shorts/Hz5dy29OMLA" className="accent">YouTube-এ দেখুন ↗</a>
            </p>
          </div>
        </section>

        <section className="section final">
          <div className="wrap narrow center">
            <img src="/logo.png" alt="" width="84" height="84" />
            <h2>আজই কথা বলে লেখা শুরু করুন</h2>
            <a className="btn primary" href={DOWNLOAD}>
              ⬇ Kothok ডাউনলোড করুন
            </a>
            <p className="muted small">Kothok-portable.zip · ভয়েস মডেলসহ · প্রায় ৩৫০ MB</p>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="wrap footer-inner">
          <span>© {new Date().getFullYear()} কথক · MIT License</span>
          <span>
            Developed by <a href="https://rotexit.com">rotexit.com</a> · <a href={REPO}>GitHub</a>
          </span>
        </div>
      </footer>
    </>
  );
}
