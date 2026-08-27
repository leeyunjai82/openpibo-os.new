from openpibo.vision_classify import CustomClassifier
import argparse

# ✅ 실행 예시
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', help='set model file path', required=True)
    parser.add_argument('--output', help='set output file path', required=True)
    args = parser.parse_args()

    model_path = args.model
    output_path = args.output
    print(model_path, output_path)
    cf = CustomClassifier()
    try:
      cf.convert_tfjs_to_keras(model_path, output_path)
    except Exception as e:
      print(f"❌ 변환 실패: {e}")
