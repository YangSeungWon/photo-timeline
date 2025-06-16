#!/usr/bin/env python3
"""
Photo EXIF Processor for Google My Maps
연속된 날짜 덩어리(chunk) 기반 사진 처리 및 Google My Maps 업로드용 데이터 생성
"""

import os
import json
import pandas as pd
import piexif
from PIL import Image
from datetime import datetime, timedelta
import subprocess
from pathlib import Path
import logging

# 로그 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PhotoExifProcessor:
    def __init__(self, photo_folder):
        """
        사진 폴더를 지정하여 EXIF 처리기 초기화

        Args:
            photo_folder (str): 사진이 저장된 폴더 경로
        """
        self.photo_folder = Path(photo_folder)
        self.supported_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".mov",
            ".mp4",
            ".heic",
            ".tiff",
        }
        self.df = pd.DataFrame()

        if not self.photo_folder.exists():
            raise ValueError(f"사진 폴더가 존재하지 않습니다: {photo_folder}")

    def scan_photos(self):
        """
        폴더 내 모든 이미지/영상 파일 검색

        Returns:
            list: 지원되는 파일 확장자의 파일 경로 리스트
        """
        photo_files = []

        for file_path in self.photo_folder.rglob("*"):
            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.supported_extensions
            ):
                photo_files.append(file_path)

        logger.info(f"총 {len(photo_files)}개의 파일을 발견했습니다.")
        return sorted(photo_files)

    def extract_exif_data(self, file_path):
        """
        단일 파일에서 EXIF 데이터 추출

        Args:
            file_path (Path): 파일 경로

        Returns:
            dict: EXIF 데이터 (FileName, DateTimeOriginal, GPSLat, GPSLong)
        """
        result = {
            "FileName": file_path.name,
            "FilePath": str(file_path),
            "DateTimeOriginal": None,
            "GPSLat": None,
            "GPSLong": None,
        }

        try:
            # 이미지 파일인 경우 piexif 사용
            if file_path.suffix.lower() in {".jpg", ".jpeg", ".tiff"}:
                exif_dict = piexif.load(str(file_path))

                # 날짜 정보 추출
                if piexif.ExifIFD.DateTimeOriginal in exif_dict.get("Exif", {}):
                    date_bytes = exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal]
                    result["DateTimeOriginal"] = date_bytes.decode("utf-8")

                # GPS 정보 추출
                gps_info = exif_dict.get("GPS", {})
                if gps_info:
                    lat = self._convert_gps_to_decimal(
                        gps_info.get(piexif.GPSIFD.GPSLatitude),
                        gps_info.get(piexif.GPSIFD.GPSLatitudeRef),
                    )
                    lon = self._convert_gps_to_decimal(
                        gps_info.get(piexif.GPSIFD.GPSLongitude),
                        gps_info.get(piexif.GPSIFD.GPSLongitudeRef),
                    )
                    result["GPSLat"] = lat
                    result["GPSLong"] = lon

            # 영상 파일의 경우 exiftool 사용 (있는 경우)
            elif file_path.suffix.lower() in {".mov", ".mp4"}:
                result.update(self._extract_video_exif(file_path))

        except Exception as e:
            logger.warning(f"EXIF 추출 실패 {file_path.name}: {e}")

        return result

    def _convert_gps_to_decimal(self, gps_coord, gps_ref):
        """
        GPS 좌표를 도분초에서 십진수로 변환
        """
        if not gps_coord or not gps_ref:
            return None

        try:
            degrees = gps_coord[0][0] / gps_coord[0][1]
            minutes = gps_coord[1][0] / gps_coord[1][1]
            seconds = gps_coord[2][0] / gps_coord[2][1]

            decimal = degrees + minutes / 60 + seconds / 3600

            if gps_ref.decode("utf-8") in ["S", "W"]:
                decimal = -decimal

            return decimal
        except:
            return None

    def _extract_video_exif(self, file_path):
        """
        영상 파일에서 exiftool을 사용하여 메타데이터 추출
        """
        result = {"DateTimeOriginal": None, "GPSLat": None, "GPSLong": None}

        try:
            # exiftool이 설치되어 있는지 확인
            cmd = ["exiftool", "-j", str(file_path)]
            output = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if output.returncode == 0:
                data = json.loads(output.stdout)[0]

                # 날짜 정보
                for date_field in ["DateTimeOriginal", "CreateDate", "MediaCreateDate"]:
                    if date_field in data:
                        result["DateTimeOriginal"] = data[date_field]
                        break

                # GPS 정보
                if "GPSLatitude" in data and "GPSLongitude" in data:
                    result["GPSLat"] = data["GPSLatitude"]
                    result["GPSLong"] = data["GPSLongitude"]

        except (
            subprocess.TimeoutExpired,
            FileNotFoundError,
            json.JSONDecodeError,
        ) as e:
            logger.warning(f"exiftool 처리 실패 {file_path.name}: {e}")

        return result

    def process_all_photos(self):
        """
        모든 사진의 EXIF 데이터를 추출하여 DataFrame 생성
        """
        photo_files = self.scan_photos()
        exif_data = []

        for i, file_path in enumerate(photo_files, 1):
            logger.info(f"처리 중 ({i}/{len(photo_files)}): {file_path.name}")
            exif_data.append(self.extract_exif_data(file_path))

        self.df = pd.DataFrame(exif_data)
        logger.info(f"총 {len(self.df)}개 파일의 EXIF 데이터를 추출했습니다.")

        return self.df

    def detect_date_chunks(self):
        """
        연속된 날짜 덩어리(chunk) 자동 탐지
        """
        if self.df.empty:
            raise ValueError("먼저 process_all_photos()를 실행해주세요.")

        # 날짜가 있는 데이터만 필터링
        date_df = self.df[self.df["DateTimeOriginal"].notna()].copy()

        if date_df.empty:
            logger.warning("날짜 정보가 있는 사진이 없습니다.")
            return self.df

        # 날짜 파싱 및 정렬 (일반적인 EXIF 날짜 형식들 시도)
        def parse_exif_date(date_str):
            """EXIF 날짜 형식을 파싱"""
            if pd.isna(date_str):
                return pd.NaT

            # 일반적인 EXIF 날짜 형식들
            formats = [
                "%Y:%m:%d %H:%M:%S",  # 표준 EXIF 형식
                "%Y-%m-%d %H:%M:%S",  # ISO 형식
                "%Y:%m:%d",  # 날짜만
                "%Y-%m-%d",  # ISO 날짜만
            ]

            for fmt in formats:
                try:
                    return pd.to_datetime(date_str, format=fmt)
                except:
                    continue

            # 모든 형식 실패 시 일반 파싱 시도
            try:
                return pd.to_datetime(date_str, errors="coerce")
            except:
                return pd.NaT

        date_df["datetime"] = date_df["DateTimeOriginal"].apply(parse_exif_date)

        # NaT 값 제거 (파싱 실패한 날짜들)
        date_df = date_df[date_df["datetime"].notna()].copy()

        if date_df.empty:
            logger.warning("유효한 날짜 정보가 있는 사진이 없습니다.")
            return self.df

        date_df["date"] = date_df["datetime"].dt.date
        date_df = date_df.sort_values("datetime")

        # 연속된 날짜 덩어리 탐지 (1일 차이 기준)
        date_diff = date_df["date"].diff()
        date_df["chunk"] = (date_diff > timedelta(days=1)).cumsum()

        # chunk_id 생성 (YYMMDD 형식) - NaT 값 안전하게 처리
        def safe_strftime(date_series):
            try:
                min_date = date_series.min()
                if pd.isna(min_date):
                    return "unknown"
                return min_date.strftime("%y%m%d")
            except (AttributeError, ValueError):
                return "unknown"

        date_df["chunk_id"] = date_df.groupby("chunk")["date"].transform(safe_strftime)

        # 원본 DataFrame에 병합
        self.df = self.df.merge(
            date_df[["FilePath", "chunk", "chunk_id", "datetime"]],
            on="FilePath",
            how="left",
        )

        # 유효한 chunk_id 개수 계산
        valid_chunks = self.df[
            self.df["chunk_id"].notna() & (self.df["chunk_id"] != "unknown")
        ]["chunk_id"].nunique()
        logger.info(f"총 {valid_chunks}개의 날짜 덩어리를 탐지했습니다.")
        return self.df

    def classify_processing_type(self):
        """
        자동 처리 vs 수동 보정 그룹 분류

        Returns:
            tuple: (자동_처리_df, 수동_날짜_df, 수동_GPS_df)
        """
        if self.df.empty:
            raise ValueError(
                "먼저 process_all_photos()와 detect_date_chunks()를 실행해주세요."
            )

        # 자동 처리: 날짜와 GPS 모두 있음
        auto_df = self.df[
            (self.df["DateTimeOriginal"].notna())
            & (self.df["GPSLat"].notna())
            & (self.df["GPSLong"].notna())
        ].copy()

        # 수동 날짜 보정: GPS는 있지만 날짜 없음
        manual_date_df = self.df[
            (self.df["DateTimeOriginal"].isna())
            & (self.df["GPSLat"].notna())
            & (self.df["GPSLong"].notna())
        ].copy()

        # 수동 GPS 보정: 날짜는 있지만 GPS 없음
        manual_gps_df = self.df[
            (self.df["DateTimeOriginal"].notna())
            & ((self.df["GPSLat"].isna()) | (self.df["GPSLong"].isna()))
        ].copy()

        # 둘 다 없는 경우
        manual_both_df = self.df[
            (self.df["DateTimeOriginal"].isna())
            & ((self.df["GPSLat"].isna()) | (self.df["GPSLong"].isna()))
        ].copy()

        logger.info(f"분류 결과:")
        logger.info(f"  자동 처리: {len(auto_df)}개")
        logger.info(f"  수동 날짜 보정: {len(manual_date_df)}개")
        logger.info(f"  수동 GPS 보정: {len(manual_gps_df)}개")
        logger.info(f"  수동 전체 보정: {len(manual_both_df)}개")

        return auto_df, manual_date_df, manual_gps_df, manual_both_df

    def add_order_column(self):
        """
        같은 chunk_id 내에서 시간순 order 컬럼 추가
        """
        if "datetime" not in self.df.columns:
            self.detect_date_chunks()

        # chunk_id가 있는 행들만 order 부여
        if "chunk_id" in self.df.columns:
            # chunk_id가 유효한 행들만 처리
            valid_mask = self.df["chunk_id"].notna() & (
                self.df["chunk_id"] != "unknown"
            )

            if valid_mask.any():
                # 유효한 chunk_id가 있는 행들에 대해서만 order 부여
                valid_df = self.df[valid_mask].copy()
                valid_df["order"] = valid_df.groupby("chunk_id")["datetime"].rank(
                    method="dense", ascending=True
                )

                # 전체 DataFrame에 order 컬럼 초기화
                self.df["order"] = 0

                # 유효한 행들의 order 값 업데이트
                self.df.loc[valid_mask, "order"] = valid_df["order"]
            else:
                # 유효한 chunk_id가 없으면 모든 order를 0으로 설정
                self.df["order"] = 0
        else:
            # chunk_id 컬럼이 없으면 모든 order를 0으로 설정
            self.df["order"] = 0

        # order 컬럼을 정수형으로 변환
        self.df["order"] = self.df["order"].fillna(0).astype(int)

        return self.df

    def get_summary(self):
        """
        처리 결과 요약 정보 반환
        """
        if self.df.empty:
            return "데이터가 없습니다. process_all_photos()를 먼저 실행해주세요."

        total_files = len(self.df)
        with_date = self.df["DateTimeOriginal"].notna().sum()
        with_gps = (self.df["GPSLat"].notna() & self.df["GPSLong"].notna()).sum()
        with_both = (
            self.df["DateTimeOriginal"].notna()
            & self.df["GPSLat"].notna()
            & self.df["GPSLong"].notna()
        ).sum()

        # 유효한 chunk_id 개수 계산
        if "chunk_id" in self.df.columns:
            chunks = self.df[
                self.df["chunk_id"].notna() & (self.df["chunk_id"] != "unknown")
            ]["chunk_id"].nunique()
        else:
            chunks = 0

        summary = f"""
=== 사진 EXIF 처리 요약 ===
전체 파일 수: {total_files}개
날짜 정보 있음: {with_date}개 ({with_date/total_files*100:.1f}%)
GPS 정보 있음: {with_gps}개 ({with_gps/total_files*100:.1f}%)
완전 자동 처리 가능: {with_both}개 ({with_both/total_files*100:.1f}%)
날짜 덩어리(chunk) 수: {chunks}개

수동 보정 필요:
- 날짜만 없음: {with_gps - with_both}개
- GPS만 없음: {with_date - with_both}개
- 둘 다 없음: {total_files - with_date - with_gps + with_both}개
"""
        return summary
