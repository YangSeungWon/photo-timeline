#!/usr/bin/env python3
"""
사진 EXIF → Google My Maps 변환기 사용 예시
"""

import sys
from pathlib import Path

from photo_exif_processor import PhotoExifProcessor
from data_exporter import DataExporter


def example_basic_usage():
    """기본 사용법 예시"""
    print("=== 기본 사용법 예시 ===")

    # 예시 폴더 경로 (실제 사용 시 변경 필요)
    photo_folder = "/Users/whysw/Pictures/🌊"

    if not Path(photo_folder).exists():
        print(f"❌ 사진 폴더가 존재하지 않습니다: {photo_folder}")
        print("실제 사진 폴더 경로로 변경해주세요.")
        return

    try:
        # 1. EXIF 데이터 처리
        print("1. EXIF 데이터 처리 시작...")
        processor = PhotoExifProcessor(photo_folder)

        # 사진 스캔 및 EXIF 추출
        df = processor.process_all_photos()
        print(f"   ✓ {len(df)}개 파일 처리 완료")

        # 연속 날짜 덩어리 탐지
        processor.detect_date_chunks()
        print("   ✓ 날짜 덩어리 탐지 완료")

        # 순서 컬럼 추가
        processor.add_order_column()
        print("   ✓ 순서 정보 생성 완료")

        # 2. 처리 결과 요약
        print("\n2. 처리 결과 요약:")
        print(processor.get_summary())

        # 3. 파일 내보내기
        print("3. 파일 내보내기...")
        exporter = DataExporter(processor)
        results = exporter.export_all()

        print("   ✓ 내보내기 완료!")
        print(f"   - 통합 CSV: {Path(results['csv']).name}")
        print(f"   - KML 파일: {Path(results['kml']).name}")
        print(f"   - 분리 CSV: {len(results['chunk_csvs'])}개")
        print(f"   - 업로드 가이드: {Path(results['guide']).name}")

        return True

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False


def example_filtered_processing():
    """필터링된 처리 예시"""
    print("\n=== 필터링된 처리 예시 ===")

    photo_folder = "/Users/whysw/Pictures/🌊"

    if not Path(photo_folder).exists():
        print(f"❌ 사진 폴더가 존재하지 않습니다: {photo_folder}")
        return

    try:
        processor = PhotoExifProcessor(photo_folder)
        df = processor.process_all_photos()
        processor.detect_date_chunks()

        # 특정 날짜 범위만 필터링
        start_date = "2025-05-10"
        end_date = "2025-05-15"

        # datetime 컬럼이 있는 경우에만 필터링
        if "datetime" in processor.df.columns:
            filtered_df = processor.df[
                (processor.df["datetime"] >= start_date)
                & (processor.df["datetime"] <= end_date)
            ]

            if not filtered_df.empty:
                print(f"날짜 범위 {start_date} ~ {end_date}:")
                print(f"- 필터링된 사진: {len(filtered_df)}개")

                # 필터링된 데이터로 내보내기
                exporter = DataExporter(processor)
                # 원본 데이터를 필터링된 데이터로 임시 교체
                original_df = exporter.processor.df.copy()
                exporter.processor.df = filtered_df

                csv_path = exporter.export_csv("filtered_export.csv")
                print(f"- 필터링된 CSV 생성: {Path(csv_path).name}")

                # 원본 데이터 복원
                exporter.processor.df = original_df
            else:
                print(f"해당 날짜 범위에 사진이 없습니다.")
        else:
            print("날짜 정보가 없어 필터링할 수 없습니다.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")


def example_chunk_analysis():
    """덩어리 분석 예시"""
    print("\n=== 덩어리 분석 예시 ===")

    photo_folder = "/Users/whysw/Pictures/🌊"

    if not Path(photo_folder).exists():
        print(f"❌ 사진 폴더가 존재하지 않습니다: {photo_folder}")
        return

    try:
        processor = PhotoExifProcessor(photo_folder)
        df = processor.process_all_photos()
        processor.detect_date_chunks()
        processor.add_order_column()

        # 자동/수동 처리 분류
        auto_df, manual_date_df, manual_gps_df, manual_both_df = (
            processor.classify_processing_type()
        )

        print("데이터 분류 결과:")
        print(f"- 자동 처리 가능: {len(auto_df)}개")
        print(f"- 날짜만 보정 필요: {len(manual_date_df)}개")
        print(f"- GPS만 보정 필요: {len(manual_gps_df)}개")
        print(f"- 전체 보정 필요: {len(manual_both_df)}개")

        # 덩어리별 상세 분석
        if "chunk_id" in processor.df.columns:
            print("\n덩어리별 상세:")
            for chunk_id, chunk_df in processor.df.groupby("chunk_id"):
                if pd.notna(chunk_id):
                    date_range = f"{chunk_df['datetime'].min().date()} ~ {chunk_df['datetime'].max().date()}"
                    complete_count = len(
                        chunk_df[
                            (chunk_df["DateTimeOriginal"].notna())
                            & (chunk_df["GPSLat"].notna())
                            & (chunk_df["GPSLong"].notna())
                        ]
                    )
                    print(
                        f"  {chunk_id}: {len(chunk_df)}개 사진, 완전한 데이터 {complete_count}개 ({date_range})"
                    )

    except Exception as e:
        print(f"❌ 오류 발생: {e}")


def main():
    """메인 함수"""
    print("사진 EXIF → Google My Maps 변환기 사용 예시")
    print("=" * 50)

    # 예시 실행
    success = example_basic_usage()

    if success:
        example_filtered_processing()
        example_chunk_analysis()

    print("\n" + "=" * 50)
    print("예시 실행 완료!")
    print("실제 사용 시에는 photo_folder 경로를 수정해주세요.")
    print("GUI 버전 실행: python main.py")


if __name__ == "__main__":
    # pandas import (분석 예시에서 사용)
    try:
        import pandas as pd
    except ImportError:
        print("pandas가 설치되지 않았습니다: pip install pandas")
        sys.exit(1)

    main()
