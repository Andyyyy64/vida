import { Hono } from 'hono';
import { getDb } from '../db.js';

// Meta-category mapping (mirrors life/activity.py)
const META_CATEGORIES: Record<string, string[]> = {
  focus: ['プログラミング', 'ドキュメント閲覧', 'コンテンツ制作', '読書'],
  communication: ['チャット', '会話'],
  entertainment: ['YouTube視聴', 'ゲーム', 'SNS', '音楽'],
  browsing: ['ブラウジング'],
  break: ['休憩', '離席', '食事'],
  idle: ['睡眠', '不在'],
};

function getMetaCategory(activity: string): string {
  for (const [meta, activities] of Object.entries(META_CATEGORIES)) {
    if (activities.includes(activity)) return meta;
  }
  return 'other';
}

const app = new Hono();

// GET /api/activities — list all activity categories with meta-categories
app.get('/', (c) => {
  const db = getDb();
  const rows = db
    .prepare(
      `SELECT activity, COUNT(*) as frame_count
       FROM frames WHERE activity != ''
       GROUP BY activity ORDER BY frame_count DESC`,
    )
    .all() as { activity: string; frame_count: number }[];

  const activities = rows.map((r) => ({
    activity: r.activity,
    metaCategory: getMetaCategory(r.activity),
    frameCount: r.frame_count,
  }));

  return c.json(activities);
});

export default app;
export { getMetaCategory, META_CATEGORIES };
