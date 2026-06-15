"""一键启动脚本。"""
import sys, os

BASE = os.path.dirname(__file__)
sys.path.insert(0, BASE)

def main():
    from backend.database import init_db
    from crawler.crawlers import inject_sample_data
    from analysis.sentiment_analysis import batch_sentiment_analysis, train_lda_model

    print("=" * 50)
    print("  金融舆情智能分析系统")
    print("=" * 50)
    print("\n[1/4] 初始化数据库...")
    init_db()
    print("[2/4] 注入示例数据...")
    inject_sample_data()
    print("[3/4] 情感分析...")
    batch_sentiment_analysis()
    print("[4/4] LDA主题建模...")
    train_lda_model()
    print("\n启动成功，浏览器访问: http://localhost:5000\n")
    from backend.app import app
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    main()
