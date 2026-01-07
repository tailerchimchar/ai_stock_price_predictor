import Link from 'next/link';
import styles from './page.module.css';

export default function Home() {
  return (
    <div className={styles.container}>
      <main className={styles.main}>
        <h1>AI Stock Price Predictor</h1>
        <p>Analyze stock market trends with our AI-powered bias assessment tool.</p>
        
        <Link href="/analyses" className={styles.primaryButton}>
          Go to Analysis Dashboard →
        </Link>

        <section className={styles.features}>
          <h2>Features</h2>
          <ul>
            <li>📊 Real-time stock analysis</li>
            <li>🤖 AI-powered bias assessment</li>
            <li>📈 Price movement tracking</li>
            <li>💾 Store and compare analyses</li>
          </ul>
        </section>
      </main>
    </div>
  );
}
