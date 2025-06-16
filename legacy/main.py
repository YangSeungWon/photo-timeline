#!/usr/bin/env python3
"""
Photo EXIF to Google My Maps - Main Application
사진 EXIF 데이터를 Google My Maps용으로 처리하는 메인 애플리케이션
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
import os
from pathlib import Path
import logging

# 로컬 모듈 import
from photo_exif_processor import PhotoExifProcessor
from manual_correction_gui import show_correction_menu
from data_exporter import DataExporter

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("photo_exif_log.txt", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class MainApplication:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("사진 EXIF → Google My Maps 변환기")
        self.root.geometry("800x600")

        self.processor = None
        self.exporter = None
        self.selected_folder = ""

        self.setup_ui()

    def setup_ui(self):
        """메인 UI 설정"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 제목
        title_label = ttk.Label(
            main_frame, text="사진 EXIF → Google My Maps 변환기", font=("", 16, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=20)

        # 설명
        desc_text = """
연속된 날짜 덩어리(chunk) 기반으로 사진의 EXIF 데이터를 처리하여
Google My Maps에 업로드할 수 있는 CSV/KML 파일을 생성합니다.

지원 파일: JPG, JPEG, PNG, MOV, MP4, HEIC, TIFF
        """
        desc_label = ttk.Label(main_frame, text=desc_text, justify=tk.CENTER)
        desc_label.grid(row=1, column=0, columnspan=2, pady=10)

        # 1단계: 폴더 선택
        step1_frame = ttk.LabelFrame(
            main_frame, text="1단계: 사진 폴더 선택", padding="10"
        )
        step1_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        self.folder_var = tk.StringVar()
        folder_entry = ttk.Entry(step1_frame, textvariable=self.folder_var, width=60)
        folder_entry.grid(row=0, column=0, padx=5)

        folder_button = ttk.Button(
            step1_frame, text="폴더 선택", command=self.select_folder
        )
        folder_button.grid(row=0, column=1, padx=5)

        # 2단계: EXIF 처리
        step2_frame = ttk.LabelFrame(
            main_frame, text="2단계: EXIF 데이터 추출 및 분석", padding="10"
        )
        step2_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        process_button = ttk.Button(
            step2_frame,
            text="EXIF 데이터 처리 시작",
            command=self.process_exif_data,
            width=30,
        )
        process_button.grid(row=0, column=0, pady=5)

        # 결과 표시 영역
        self.result_text = tk.Text(step2_frame, height=8, width=70)
        self.result_text.grid(row=1, column=0, pady=10)

        scrollbar = ttk.Scrollbar(
            step2_frame, orient="vertical", command=self.result_text.yview
        )
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        self.result_text.configure(yscrollcommand=scrollbar.set)

        # 3단계: 단계별 보정
        step3_frame = ttk.LabelFrame(
            main_frame, text="3단계: 단계별 보정 (선택사항)", padding="10"
        )
        step3_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        correction_button = ttk.Button(
            step3_frame,
            text="단계별 보정 시작",
            command=self.start_manual_correction,
            width=30,
        )
        correction_button.grid(row=0, column=0, pady=5)

        # 4단계: 내보내기
        step4_frame = ttk.LabelFrame(
            main_frame, text="4단계: Google My Maps용 파일 생성", padding="10"
        )
        step4_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        export_frame = ttk.Frame(step4_frame)
        export_frame.grid(row=0, column=0)

        ttk.Button(export_frame, text="CSV 내보내기", command=self.export_csv).grid(
            row=0, column=0, padx=5
        )
        ttk.Button(export_frame, text="KML 내보내기", command=self.export_kml).grid(
            row=0, column=1, padx=5
        )
        ttk.Button(export_frame, text="전체 내보내기", command=self.export_all).grid(
            row=0, column=2, padx=5
        )

        # 상태바
        self.status_var = tk.StringVar()
        self.status_var.set("폴더를 선택하여 시작하세요.")
        status_bar = ttk.Label(
            main_frame, textvariable=self.status_var, relief=tk.SUNKEN
        )
        status_bar.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        # 그리드 설정
        main_frame.columnconfigure(0, weight=1)
        step1_frame.columnconfigure(0, weight=1)
        step2_frame.columnconfigure(0, weight=1)
        step3_frame.columnconfigure(0, weight=1)
        step4_frame.columnconfigure(0, weight=1)

    def select_folder(self):
        """사진 폴더 선택"""
        folder = filedialog.askdirectory(title="사진이 저장된 폴더를 선택하세요")
        if folder:
            self.folder_var.set(folder)
            self.selected_folder = folder
            self.status_var.set(f"선택된 폴더: {folder}")
            logger.info(f"사진 폴더 선택: {folder}")

    def process_exif_data(self):
        """EXIF 데이터 처리"""
        if not self.selected_folder:
            messagebox.showwarning("경고", "먼저 사진 폴더를 선택해주세요.")
            return

        try:
            self.status_var.set("EXIF 데이터 처리 중...")
            self.root.update()

            # 처리기 초기화
            self.processor = PhotoExifProcessor(self.selected_folder)

            # EXIF 데이터 추출
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, "사진 파일 스캔 중...\n")
            self.root.update()

            df = self.processor.process_all_photos()
            self.result_text.insert(
                tk.END, f"✓ {len(df)}개 파일의 EXIF 데이터 추출 완료\n"
            )
            self.root.update()

            # 날짜 덩어리 탐지
            self.result_text.insert(tk.END, "연속 날짜 덩어리 탐지 중...\n")
            self.root.update()

            self.processor.detect_date_chunks()
            self.result_text.insert(tk.END, "✓ 날짜 덩어리 탐지 완료\n")
            self.root.update()

            # 분류 결과
            auto_df, manual_date_df, manual_gps_df, manual_both_df = (
                self.processor.classify_processing_type()
            )

            # 순서 컬럼 추가
            self.processor.add_order_column()

            # 결과 요약 표시
            summary = self.processor.get_summary()
            self.result_text.insert(tk.END, "\n" + summary)

            # 내보내기 준비
            self.exporter = DataExporter(self.processor)
            self.status_var.set("EXIF 데이터 처리 완료!")

            logger.info("EXIF 데이터 처리 완료")

        except Exception as e:
            error_msg = f"EXIF 처리 중 오류 발생: {e}"
            self.result_text.insert(tk.END, f"\n❌ {error_msg}\n")
            self.status_var.set("처리 실패")
            logger.error(error_msg)
            messagebox.showerror("오류", error_msg)

    def start_manual_correction(self):
        """단계별 보정 시작"""
        if not self.processor:
            messagebox.showwarning("경고", "먼저 EXIF 데이터 처리를 완료해주세요.")
            return

        try:
            self.status_var.set("단계별 보정 GUI 실행 중...")
            show_correction_menu(self.processor)
            self.status_var.set("단계별 보정 완료")

            # 보정 후 순서 재계산
            self.processor.add_order_column()

        except Exception as e:
            error_msg = f"단계별 보정 중 오류 발생: {e}"
            self.status_var.set("단계별 보정 실패")
            logger.error(error_msg)
            messagebox.showerror("오류", error_msg)

    def export_csv(self):
        """CSV 내보내기"""
        if not self.exporter:
            messagebox.showwarning("경고", "먼저 EXIF 데이터 처리를 완료해주세요.")
            return

        try:
            self.status_var.set("CSV 파일 생성 중...")
            csv_path = self.exporter.export_csv()
            self.status_var.set("CSV 내보내기 완료!")

            messagebox.showinfo("완료", f"CSV 파일이 생성되었습니다:\n{csv_path}")

        except Exception as e:
            error_msg = f"CSV 내보내기 중 오류 발생: {e}"
            self.status_var.set("CSV 내보내기 실패")
            logger.error(error_msg)
            messagebox.showerror("오류", error_msg)

    def export_kml(self):
        """KML 내보내기"""
        if not self.exporter:
            messagebox.showwarning("경고", "먼저 EXIF 데이터 처리를 완료해주세요.")
            return

        try:
            self.status_var.set("KML 파일 생성 중...")
            kml_path = self.exporter.export_kml()
            self.status_var.set("KML 내보내기 완료!")

            messagebox.showinfo("완료", f"KML 파일이 생성되었습니다:\n{kml_path}")

        except Exception as e:
            error_msg = f"KML 내보내기 중 오류 발생: {e}"
            self.status_var.set("KML 내보내기 실패")
            logger.error(error_msg)
            messagebox.showerror("오류", error_msg)

    def export_all(self):
        """모든 형식으로 내보내기"""
        if not self.exporter:
            messagebox.showwarning("경고", "먼저 EXIF 데이터 처리를 완료해주세요.")
            return

        try:
            self.status_var.set("모든 파일 생성 중...")
            self.root.update()

            results = self.exporter.export_all()

            self.status_var.set("모든 파일 내보내기 완료!")

            # 결과 표시
            result_msg = f"""
내보내기 완료!

생성된 파일:
• 통합 CSV: {Path(results['csv']).name}
• KML 파일: {Path(results['kml']).name}
• 분리 CSV: {len(results['chunk_csvs'])}개 파일
• 업로드 가이드: {Path(results['guide']).name}
• 처리 요약: {Path(results['summary']).name}

모든 파일은 'output' 폴더에 저장되었습니다.
Google My Maps 업로드 가이드를 참조하세요.
"""

            messagebox.showinfo("완료", result_msg)

            # output 폴더 열기 (운영체제별)
            if messagebox.askyesno("폴더 열기", "생성된 파일들이 있는 폴더를 열까요?"):
                self.open_output_folder()

        except Exception as e:
            error_msg = f"파일 내보내기 중 오류 발생: {e}"
            self.status_var.set("내보내기 실패")
            logger.error(error_msg)
            messagebox.showerror("오류", error_msg)

    def open_output_folder(self):
        """output 폴더 열기"""
        output_path = Path("output").absolute()
        try:
            if sys.platform == "win32":
                os.startfile(output_path)
            elif sys.platform == "darwin":  # macOS
                os.system(f"open '{output_path}'")
            else:  # Linux
                os.system(f"xdg-open '{output_path}'")
        except Exception as e:
            logger.warning(f"폴더 열기 실패: {e}")

    def run(self):
        """애플리케이션 실행"""
        self.root.mainloop()


def check_dependencies():
    """필요한 의존성 확인"""
    missing_modules = []

    try:
        import pandas
    except ImportError:
        missing_modules.append("pandas")

    try:
        import piexif
    except ImportError:
        missing_modules.append("piexif")

    try:
        from PIL import Image
    except ImportError:
        missing_modules.append("Pillow")

    try:
        import folium
    except ImportError:
        missing_modules.append("folium")

    try:
        import simplekml
    except ImportError:
        missing_modules.append("simplekml")

    if missing_modules:
        error_msg = f"""
필요한 Python 패키지가 설치되지 않았습니다:
{', '.join(missing_modules)}

다음 명령어로 설치해주세요:
pip install {' '.join(missing_modules)}

또는:
pip install -r requirements.txt
"""
        print(error_msg)
        input("Enter 키를 눌러 종료하세요...")
        sys.exit(1)


def main():
    """메인 함수"""
    print("=== 사진 EXIF → Google My Maps 변환기 ===")
    print("의존성 확인 중...")

    check_dependencies()

    print("애플리케이션 시작 중...")

    try:
        app = MainApplication()
        app.run()
    except Exception as e:
        logger.error(f"애플리케이션 실행 중 오류: {e}")
        messagebox.showerror(
            "치명적 오류", f"애플리케이션 실행 중 오류가 발생했습니다:\n{e}"
        )


if __name__ == "__main__":
    main()
 